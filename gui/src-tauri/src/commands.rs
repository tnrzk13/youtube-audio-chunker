use crate::sidecar::{SidecarError, SidecarManager};
use serde_json::Value;
use tauri::State;
use tokio::sync::Mutex;

pub type ManagedSidecar = Mutex<SidecarManager>;

#[tauri::command]
pub async fn get_library(
    sidecar: State<'_, ManagedSidecar>,
) -> Result<Value, SidecarError> {
    sidecar.lock().await.call("get_library", Value::Null).await
}

#[tauri::command]
pub async fn get_garmin_status(
    sidecar: State<'_, ManagedSidecar>,
) -> Result<Value, SidecarError> {
    sidecar
        .lock()
        .await
        .call("get_garmin_status", Value::Null)
        .await
}

#[tauri::command]
pub async fn add_to_queue(
    sidecar: State<'_, ManagedSidecar>,
    urls: Vec<String>,
    content_type: String,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({
        "urls": urls,
        "content_type": content_type,
    });
    sidecar.lock().await.call("add_to_queue", params).await
}

#[tauri::command]
pub async fn remove_episode(
    sidecar: State<'_, ManagedSidecar>,
    video_id: String,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({ "video_id": video_id });
    sidecar.lock().await.call("remove_episode", params).await
}

#[tauri::command]
pub async fn remove_from_garmin(
    sidecar: State<'_, ManagedSidecar>,
    folder_name: String,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({ "folder_name": folder_name });
    sidecar
        .lock()
        .await
        .call("remove_from_garmin", params)
        .await
}

#[tauri::command]
pub async fn process_queue(
    sidecar: State<'_, ManagedSidecar>,
    chunk_duration_seconds: Option<u32>,
    artist: Option<String>,
    keep_full: Option<bool>,
    no_transfer: Option<bool>,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({
        "chunk_duration_seconds": chunk_duration_seconds,
        "artist": artist,
        "keep_full": keep_full.unwrap_or(false),
        "no_transfer": no_transfer.unwrap_or(false),
    });
    sidecar.lock().await.call("process_queue", params).await
}

#[tauri::command]
pub async fn transfer_unsynced(
    sidecar: State<'_, ManagedSidecar>,
) -> Result<Value, SidecarError> {
    sidecar
        .lock()
        .await
        .call("transfer_unsynced", Value::Null)
        .await
}

#[tauri::command]
pub async fn get_settings(
    sidecar: State<'_, ManagedSidecar>,
) -> Result<Value, SidecarError> {
    sidecar.lock().await.call("get_settings", Value::Null).await
}

#[tauri::command]
pub async fn save_settings(
    sidecar: State<'_, ManagedSidecar>,
    settings: Value,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({ "settings": settings });
    sidecar.lock().await.call("save_settings", params).await
}
