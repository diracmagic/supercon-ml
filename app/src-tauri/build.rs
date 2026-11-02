fn main() {
    tauri_build::try_build(
        tauri_build::Attributes::new().app_manifest(
            tauri_build::AppManifest::new().commands(&["download_app_update", "install_app_update",
                "begin_team_sign_in", "complete_team_sign_in", "native_team_request", "clear_team_session", "cancel_team_sign_in"]),
        ),
    ).expect("failed to build application permissions")
}
