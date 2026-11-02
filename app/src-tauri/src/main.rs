// Hide the console window on Windows release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod updates;
mod team_auth;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(updates::UpdateState::default())
        .manage(team_auth::TeamAuthState::default())
        .invoke_handler(tauri::generate_handler![updates::download_app_update, updates::install_app_update,
            team_auth::begin_team_sign_in, team_auth::complete_team_sign_in,
            team_auth::native_team_request, team_auth::clear_team_session, team_auth::cancel_team_sign_in])
        .run(tauri::generate_context!())
        .expect("failed to start Supercon Progress");
}
