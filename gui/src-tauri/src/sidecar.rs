use serde_json::Value;
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Emitter};
use tokio::sync::oneshot;

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

        let mut child = Command::new(&python)
            .args(["-m", "youtube_audio_chunker.sidecar"])
            .env("PATH", augmented_path())
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("Failed to spawn sidecar: {e}"))?;

        let stdin = child.stdin.take().ok_or("Failed to get sidecar stdin")?;
        let stdout = child.stdout.take().ok_or("Failed to get sidecar stdout")?;

        let pending: PendingMap = Arc::new(Mutex::new(HashMap::new()));
        let stdin = Arc::new(Mutex::new(stdin));

        // Background thread: read stdout lines and route them
        let pending_clone = pending.clone();
        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);

            for line in reader.lines() {
                let line = match line {
                    Ok(l) => l,
                    Err(_) => break,
                };
                if line.is_empty() {
                    continue;
                }

                let parsed: Value = match serde_json::from_str(&line) {
                    Ok(v) => v,
                    Err(e) => {
                        log::warn!("Sidecar sent non-JSON: {e}: {line}");
                        continue;
                    }
                };

                if let Some(id) = parsed.get("id") {
                    if parsed.get("method").is_some() {
                        // Reverse request from sidecar (e.g. confirm_removal)
                        handle_reverse_request(&app_handle, &parsed);
                    } else {
                        // Response to our request
                        let id = id.as_u64().unwrap_or(0);
                        let mut map = pending_clone.lock().unwrap();
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
            let mut map = self.pending.lock().unwrap();
            map.insert(id, tx);
        }

        let line = serde_json::to_string(&request).unwrap() + "\n";
        {
            let mut stdin = self.stdin.lock().unwrap();
            stdin
                .write_all(line.as_bytes())
                .map_err(|e| SidecarError {
                    code: -32000,
                    message: format!("Failed to write to sidecar: {e}"),
                })?;
            stdin.flush().map_err(|e| SidecarError {
                code: -32000,
                message: format!("Failed to flush sidecar stdin: {e}"),
            })?;
        }

        rx.await.map_err(|_| SidecarError {
            code: -32000,
            message: "Sidecar channel closed".to_string(),
        })?
    }

    /// Send a JSON-RPC response to a reverse request from the sidecar.
    pub fn respond_to_reverse_request(
        &self,
        request_id: Value,
        result: Value,
    ) -> Result<(), SidecarError> {
        let response = serde_json::json!({
            "jsonrpc": "2.0",
            "result": result,
            "id": request_id,
        });
        let line = serde_json::to_string(&response).unwrap() + "\n";
        let mut stdin = self.stdin.lock().unwrap();
        stdin
            .write_all(line.as_bytes())
            .map_err(|e| SidecarError {
                code: -32000,
                message: format!("Failed to write to sidecar: {e}"),
            })?;
        stdin.flush().map_err(|e| SidecarError {
            code: -32000,
            message: format!("Failed to flush sidecar stdin: {e}"),
        })?;
        Ok(())
    }
}

fn handle_reverse_request(app_handle: &AppHandle, request: &Value) {
    let method = request["method"].as_str().unwrap_or("");
    let params = request.get("params").cloned().unwrap_or(Value::Null);
    let id = request.get("id").cloned().unwrap_or(Value::Null);

    // Include the request ID so the frontend can respond via
    // the respond_to_reverse_request command.
    let mut payload = serde_json::Map::new();
    if let Value::Object(p) = params {
        payload = p;
    }
    payload.insert("_request_id".to_string(), id);

    let event_name = format!("sidecar:reverse:{method}");
    let _ = app_handle.emit(&event_name, &Value::Object(payload));
}

/// Build a PATH that includes common user-managed Python install dirs so that
/// the sidecar process works even when the app is launched from a desktop
/// shortcut (which inherits only the minimal system PATH, omitting e.g. pyenv).
fn augmented_path() -> String {
    let system_path = std::env::var("PATH").unwrap_or_default();
    let mut extra: Vec<String> = Vec::new();

    if let Ok(home) = std::env::var("HOME") {
        extra.push(format!("{home}/.pyenv/shims"));
        extra.push(format!("{home}/.pyenv/bin"));
        extra.push(format!("{home}/.local/bin"));
        extra.push(format!("{home}/anaconda3/bin"));
        extra.push(format!("{home}/miniconda3/bin"));
        extra.push(format!("{home}/mambaforge/bin"));
    }

    // Prepend extra dirs so they take priority over the minimal system PATH.
    let mut parts: Vec<&str> = extra.iter().map(String::as_str).collect();
    if !system_path.is_empty() {
        parts.push(&system_path);
    }
    parts.join(":")
}

fn find_python() -> Option<String> {
    let mut candidates = vec!["python3".to_string(), "python".to_string()];

    // Desktop-launched apps don't inherit shell PATH (e.g. pyenv shims).
    // Add common non-system install locations so the sidecar can be found.
    if let Ok(home) = std::env::var("HOME") {
        candidates.push(format!("{home}/.pyenv/shims/python3"));
        candidates.push(format!("{home}/.pyenv/shims/python"));
        candidates.push(format!("{home}/.local/bin/python3"));
        candidates.push(format!("{home}/anaconda3/bin/python3"));
        candidates.push(format!("{home}/miniconda3/bin/python3"));
        candidates.push(format!("{home}/mambaforge/bin/python3"));
    }

    // Prefer a Python that already has the sidecar module installed.
    let mut first_working = None;
    for candidate in &candidates {
        if !python_runs(candidate) {
            continue;
        }
        if first_working.is_none() {
            first_working = Some(candidate.clone());
        }
        if module_importable(candidate) {
            return Some(candidate.clone());
        }
    }

    first_working
}

fn python_runs(python: &str) -> bool {
    Command::new(python)
        .arg("--version")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .is_ok()
}

fn module_importable(python: &str) -> bool {
    Command::new(python)
        .args(["-c", "import youtube_audio_chunker"])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}
