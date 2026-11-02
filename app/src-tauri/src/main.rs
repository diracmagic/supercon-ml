// Hide the console window on Windows release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod updates;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(updates::UpdateState::default())
        .invoke_handler(tauri::generate_handler![updates::download_app_update, updates::install_app_update])
        .run(tauri::generate_context!())
        .expect("failed to start Supercon Progress");
}
