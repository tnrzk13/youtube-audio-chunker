use serde_json::Value;
use std::collections::HashMap;
use std::process::Stdio;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use tauri::{AppHandle, Emitter};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, ChildStdin};
use tokio::sync::{oneshot, Mutex};

static NEXT_ID: AtomicU64 = AtomicU64::new(1);

type PendingMap = Arc<Mutex<HashMap<u64, oneshot::Sender<Result<Value, SidecarError>>>>>;

#[derive(Debug, Clone, serde::Serialize)]
pub struct SidecarError {
    pub code: i64,
    pub message: String,
}

impl std::fmt::Display for SidecarError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.message)
    }
}

pub struct SidecarManager {
    stdin: Arc<Mutex<ChildStdin>>,
    pending: PendingMap,
    _child: Child,
}

impl SidecarManager {
    pub fn spawn(app_handle: AppHandle) -> Result<Self, String> {
        let python = find_python().ok_or("Python not found on PATH")?;

        let mut child = tokio::process::Command::new(&python)
            .args(["-m", "youtube_audio_chunker.sidecar"])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("Failed to spawn sidecar: {e}"))?;

        let stdin = child.stdin.take().ok_or("Failed to get sidecar stdin")?;
        let stdout = child.stdout.take().ok_or("Failed to get sidecar stdout")?;

        let pending: PendingMap = Arc::new(Mutex::new(HashMap::new()));
        let stdin = Arc::new(Mutex::new(stdin));

        // Background task: read stdout lines and route them
        let pending_clone = pending.clone();
        let stdin_clone = stdin.clone();
        tokio::spawn(async move {
            let reader = BufReader::new(stdout);
            let mut lines = reader.lines();

            while let Ok(Some(line)) = lines.next_line().await {
                let parsed: Value = match serde_json::from_str(&line) {
                    Ok(v) => v,
                    Err(e) => {
                        log::warn!("Sidecar sent non-JSON: {e}: {line}");
                        continue;
                    }
                };

                if let Some(id) = parsed.get("id") {
                    // Check if this is a response (has "result" or "error") or a
                    // reverse request (has "method")
                    if parsed.get("method").is_some() {
                        // Reverse request from sidecar (e.g. confirm_removal)
                        handle_reverse_request(
                            &app_handle,
                            &stdin_clone,
                            &parsed,
                        )
                        .await;
                    } else {
                        // Response to our request
                        let id = id.as_u64().unwrap_or(0);
                        let mut map = pending_clone.lock().await;
                        if let Some(sender) = map.remove(&id) {
                            if let Some(error) = parsed.get("error") {
                                let code =
                                    error.get("code").and_then(|c| c.as_i64()).unwrap_or(-1);
                                let message = error
                                    .get("message")
                                    .and_then(|m| m.as_str())
                                    .unwrap_or("Unknown error")
                                    .to_string();
                                let _ = sender.send(Err(SidecarError { code, message }));
                            } else {
                                let result =
                                    parsed.get("result").cloned().unwrap_or(Value::Null);
                                let _ = sender.send(Ok(result));
                            }
                        }
                    }
                } else if parsed.get("method").is_some() {
                    // Notification (no id) - emit as Tauri event
                    let method = parsed["method"].as_str().unwrap_or("unknown");
                    let params = parsed.get("params").cloned().unwrap_or(Value::Null);
                    let _ = app_handle.emit(&format!("sidecar:{method}"), params);
                }
            }

            log::info!("Sidecar stdout reader exited");
        });

        Ok(Self {
            stdin,
            pending,
            _child: child,
        })
    }

    pub async fn call(
        &self,
        method: &str,
        params: Value,
    ) -> Result<Value, SidecarError> {
        let id = NEXT_ID.fetch_add(1, Ordering::Relaxed);
        let request = serde_json::json!({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": id,
        });

        let (tx, rx) = oneshot::channel();
        {
            let mut map = self.pending.lock().await;
            map.insert(id, tx);
        }

        let line = serde_json::to_string(&request).unwrap() + "\n";
        {
            let mut stdin = self.stdin.lock().await;
            stdin
                .write_all(line.as_bytes())
                .await
                .map_err(|e| SidecarError {
                    code: -32000,
                    message: format!("Failed to write to sidecar: {e}"),
                })?;
            stdin.flush().await.map_err(|e| SidecarError {
                code: -32000,
                message: format!("Failed to flush sidecar stdin: {e}"),
            })?;
        }

        rx.await.map_err(|_| SidecarError {
            code: -32000,
            message: "Sidecar channel closed".to_string(),
        })?
    }
}

async fn handle_reverse_request(
    app_handle: &AppHandle,
    stdin: &Arc<Mutex<ChildStdin>>,
    request: &Value,
) {
    let method = request["method"].as_str().unwrap_or("");
    let params = request.get("params").cloned().unwrap_or(Value::Null);
    let id = request.get("id").cloned().unwrap_or(Value::Null);

    // Emit event to frontend and wait for response via a one-shot channel
    // stored in the app state
    let event_name = format!("sidecar:reverse:{method}");
    let _ = app_handle.emit(&event_name, &params);

    // For now, auto-decline reverse requests (the frontend will override this
    // by responding via a Tauri command that writes to sidecar stdin)
    let response = serde_json::json!({
        "jsonrpc": "2.0",
        "result": false,
        "id": id,
    });
    let line = serde_json::to_string(&response).unwrap() + "\n";
    let mut stdin_guard = stdin.lock().await;
    let _ = stdin_guard.write_all(line.as_bytes()).await;
    let _ = stdin_guard.flush().await;
}

fn find_python() -> Option<String> {
    for name in &["python3", "python"] {
        if std::process::Command::new(name)
            .arg("--version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .is_ok()
        {
            return Some(name.to_string());
        }
    }
    None
}
