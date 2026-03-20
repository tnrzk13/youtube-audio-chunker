mod commands;
mod sidecar;

use commands::ManagedSidecar;
use sidecar::SidecarManager;
use tauri::Manager;
use tokio::sync::Mutex;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let handle = app.handle().clone();
            let manager = SidecarManager::spawn(handle)
                .map_err(|e| Box::<dyn std::error::Error>::from(e))?;
            app.manage::<ManagedSidecar>(Mutex::new(manager));

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::get_library,
            commands::get_garmin_status,
            commands::add_to_queue,
            commands::remove_episode,
            commands::remove_episodes,
            commands::remove_from_garmin,
            commands::process_queue,
            commands::cancel,
            commands::transfer_unsynced,
            commands::transfer_episode,
            commands::get_settings,
            commands::save_settings,
            commands::respond_to_reverse_request,
            commands::list_shows,
            commands::rename_show,
            commands::edit_episode,
            commands::resync_episode,
            commands::edit_queue_entry,
            commands::search_youtube,
            commands::list_channel_videos,
            commands::list_subscriptions,
            commands::list_home_feed,
            commands::list_liked_videos,
            commands::list_playlists,
            commands::list_playlist_videos,
            commands::detect_browser,
            commands::connect_cookies,
            commands::get_auth_status,
            commands::disconnect_auth,
            commands::extract_topics,
            commands::search_topic,
            commands::delete_topic,
            commands::dismiss_video,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
