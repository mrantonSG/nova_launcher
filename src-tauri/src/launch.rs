//! Commands for opening external resources in the OS default handler.
//!
//! URLs are handed to the system browser via `tauri-plugin-opener`; launching
//! an installed app by name (Docker Desktop) falls back to the platform `open`
//! utility, which is best-effort and fails gracefully.

use tauri_plugin_opener::open_url;

use crate::actions::command_error;

/// Opens the local Nova dashboard in the default browser: `http://localhost:5001`.
#[tauri::command]
pub fn open_dashboard() -> Result<(), String> {
    open_url("http://localhost:5001", None::<&str>)
        .map_err(|e| format!("failed to open the dashboard: {e}"))
}

/// Opens Docker's download page in the default browser.
#[tauri::command]
pub fn open_docker_download() -> Result<(), String> {
    open_url(
        "https://www.docker.com/products/docker-desktop/",
        None::<&str>,
    )
    .map_err(|e| format!("failed to open the Docker download page: {e}"))
}

/// Best-effort launch of Docker Desktop on macOS via `open -a Docker`.
///
/// Fails gracefully (returning the OS error) when `open` is unavailable
/// (non-macOS) or Docker Desktop isn't installed.
#[tauri::command]
pub async fn launch_docker() -> Result<(), String> {
    let output = tokio::process::Command::new("open")
        .arg("-a")
        .arg("Docker")
        .output()
        .await
        .map_err(|e| format!("failed to run `open`: {e}"))?;
    if output.status.success() {
        Ok(())
    } else {
        Err(command_error(&output))
    }
}
