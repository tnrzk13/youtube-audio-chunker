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
    show_name: Option<String>,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({
        "urls": urls,
        "content_type": content_type,
        "show_name": show_name,
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
pub async fn transfer_episode(
    sidecar: State<'_, ManagedSidecar>,
    video_id: String,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({ "video_id": video_id });
    sidecar.lock().await.call("transfer_episode", params).await
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
pub async fn cancel(
    sidecar: State<'_, ManagedSidecar>,
) -> Result<Value, SidecarError> {
    sidecar.lock().await.call("cancel", Value::Null).await
}

#[tauri::command]
pub async fn respond_to_reverse_request(
    sidecar: State<'_, ManagedSidecar>,
    request_id: Value,
    result: Value,
) -> Result<(), SidecarError> {
    sidecar
        .lock()
        .await
        .respond_to_reverse_request(request_id, result)
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

#[tauri::command]
pub async fn list_shows(
    sidecar: State<'_, ManagedSidecar>,
) -> Result<Value, SidecarError> {
    sidecar.lock().await.call("list_shows", Value::Null).await
}

#[tauri::command]
pub async fn rename_show(
    sidecar: State<'_, ManagedSidecar>,
    old_name: String,
    new_name: String,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({
        "old_name": old_name,
        "new_name": new_name,
    });
    sidecar.lock().await.call("rename_show", params).await
}

#[tauri::command]
pub async fn edit_episode(
    sidecar: State<'_, ManagedSidecar>,
    video_id: String,
    updates: Value,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({
        "video_id": video_id,
        "updates": updates,
    });
    sidecar.lock().await.call("edit_episode", params).await
}

#[tauri::command]
pub async fn resync_episode(
    sidecar: State<'_, ManagedSidecar>,
    video_id: String,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({ "video_id": video_id });
    sidecar.lock().await.call("resync_episode", params).await
}

#[tauri::command]
pub async fn edit_queue_entry(
    sidecar: State<'_, ManagedSidecar>,
    video_id: String,
    updates: Value,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({
        "video_id": video_id,
        "updates": updates,
    });
    sidecar
        .lock()
        .await
        .call("edit_queue_entry", params)
        .await
}

#[tauri::command]
pub async fn search_youtube(
    sidecar: State<'_, ManagedSidecar>,
    query: String,
    offset: Option<u32>,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({ "query": query, "offset": offset.unwrap_or(0) });
    sidecar.lock().await.call("search_youtube", params).await
}

#[tauri::command]
pub async fn list_channel_videos(
    sidecar: State<'_, ManagedSidecar>,
    channel_url: String,
    offset: Option<u32>,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({ "channel_url": channel_url, "offset": offset.unwrap_or(0) });
    sidecar
        .lock()
        .await
        .call("list_channel_videos", params)
        .await
}

#[tauri::command]
pub async fn list_subscriptions(
    sidecar: State<'_, ManagedSidecar>,
    offset: Option<u32>,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({ "offset": offset.unwrap_or(0) });
    sidecar.lock().await.call("list_subscriptions", params).await
}

#[tauri::command]
pub async fn list_home_feed(
    sidecar: State<'_, ManagedSidecar>,
    offset: Option<u32>,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({ "offset": offset.unwrap_or(0) });
    sidecar.lock().await.call("list_home_feed", params).await
}

#[tauri::command]
pub async fn list_liked_videos(
    sidecar: State<'_, ManagedSidecar>,
    offset: Option<u32>,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({ "offset": offset.unwrap_or(0) });
    sidecar
        .lock()
        .await
        .call("list_liked_videos", params)
        .await
}

#[tauri::command]
pub async fn list_playlists(
    sidecar: State<'_, ManagedSidecar>,
) -> Result<Value, SidecarError> {
    sidecar
        .lock()
        .await
        .call("list_playlists", Value::Null)
        .await
}

#[tauri::command]
pub async fn list_playlist_videos(
    sidecar: State<'_, ManagedSidecar>,
    playlist_id: String,
    offset: Option<u32>,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({ "playlist_id": playlist_id, "offset": offset.unwrap_or(0) });
    sidecar
        .lock()
        .await
        .call("list_playlist_videos", params)
        .await
}

#[tauri::command]
pub async fn detect_browser(
    sidecar: State<'_, ManagedSidecar>,
) -> Result<Value, SidecarError> {
    sidecar
        .lock()
        .await
        .call("detect_browser", Value::Null)
        .await
}

#[tauri::command]
pub async fn connect_cookies(
    sidecar: State<'_, ManagedSidecar>,
    browser: Option<String>,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({ "browser": browser });
    sidecar.lock().await.call("connect_cookies", params).await
}

#[tauri::command]
pub async fn get_auth_status(
    sidecar: State<'_, ManagedSidecar>,
) -> Result<Value, SidecarError> {
    sidecar
        .lock()
        .await
        .call("get_auth_status", Value::Null)
        .await
}

#[tauri::command]
pub async fn disconnect_auth(
    sidecar: State<'_, ManagedSidecar>,
) -> Result<Value, SidecarError> {
    sidecar
        .lock()
        .await
        .call("disconnect_auth", Value::Null)
        .await
}

#[tauri::command]
pub async fn extract_topics(
    sidecar: State<'_, ManagedSidecar>,
) -> Result<Value, SidecarError> {
    sidecar
        .lock()
        .await
        .call("extract_topics", Value::Null)
        .await
}

#[tauri::command]
pub async fn search_topic(
    sidecar: State<'_, ManagedSidecar>,
    topic_id: String,
    page_token: Option<String>,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({
        "topic_id": topic_id,
        "page_token": page_token,
    });
    sidecar.lock().await.call("search_topic", params).await
}

#[tauri::command]
pub async fn delete_topic(
    sidecar: State<'_, ManagedSidecar>,
    topic_id: String,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({ "topic_id": topic_id });
    sidecar.lock().await.call("delete_topic", params).await
}

#[tauri::command]
pub async fn dismiss_video(
    sidecar: State<'_, ManagedSidecar>,
    video_id: String,
) -> Result<Value, SidecarError> {
    let params = serde_json::json!({ "video_id": video_id });
    sidecar.lock().await.call("dismiss_video", params).await
}
