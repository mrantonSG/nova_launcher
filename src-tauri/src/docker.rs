//! Read-only Docker / Nova status checks exposed as Tauri commands.
//!
//! Every command here is a pure check with no side effects: nothing is
//! started, stopped, created, or modified. They only report on the current
//! state of the Docker CLI, the Nova installation, and the local dashboard.

use std::env;
use std::path::{Path, PathBuf};
use std::time::Duration;

/// Returns `true` if the `docker` binary is present on `PATH`.
#[tauri::command]
pub fn docker_installed() -> bool {
    which_in_path("docker").is_some()
}

/// Returns `true` if the Docker daemon is up and answers `docker info`.
/// Returns `false` if the daemon is unreachable or the call does not finish
/// within 10 seconds.
#[tauri::command]
pub async fn docker_daemon_running() -> bool {
    let mut cmd = tokio::process::Command::new("docker");
    cmd.arg("info");
    match tokio::time::timeout(Duration::from_secs(10), cmd.output()).await {
        Ok(Ok(output)) => output.status.success(),
        _ => false,
    }
}

/// Returns `true` if the Nova compose file exists at `~/nova/docker-compose.yml`.
#[tauri::command]
pub fn nova_installed() -> bool {
    dirs::home_dir()
        .map(|home| home.join("nova").join("docker-compose.yml").is_file())
        .unwrap_or(false)
}

/// Returns the `docker ps` status string for the `nova-tracker` container
/// (e.g. `"Up 3 hours (healthy)"`), or an empty string when the container is
/// not running or the daemon is unavailable.
#[tauri::command]
pub async fn container_status() -> String {
    let mut cmd = tokio::process::Command::new("docker");
    cmd.arg("ps");
    cmd.arg("--filter");
    cmd.arg("name=nova-tracker");
    cmd.arg("--format");
    cmd.arg("{{.Status}}");
    // 10s safety timeout (consistent with docker_daemon_running) so the UI
    // never blocks on a wedged Docker daemon.
    match tokio::time::timeout(Duration::from_secs(10), cmd.output()).await {
        Ok(Ok(output)) if output.status.success() => {
            String::from_utf8_lossy(&output.stdout).trim().to_string()
        }
        _ => String::new(),
    }
}

/// Returns `true` if the local Nova dashboard answers
/// `GET http://localhost:5001` with HTTP 200 and a body larger than 500
/// bytes, within 2 seconds.
#[tauri::command]
pub async fn dashboard_reachable() -> bool {
    // ureq is a blocking client, so run it off the async runtime thread.
    tokio::task::spawn_blocking(|| {
        match ureq::get("http://localhost:5001")
            .timeout(Duration::from_secs(2))
            .call()
        {
            Ok(resp) => {
                resp.status() == 200
                    && matches!(resp.into_string(), Ok(body) if body.len() > 500)
            }
            Err(_) => false,
        }
    })
    .await
    .unwrap_or(false)
}

/// Walks the app's readiness decision chain and returns a single state string
/// the frontend can switch on, in order of increasing readiness:
///
/// - `docker_missing` — the `docker` binary is not on `PATH`
/// - `docker_stopped` — Docker is installed but the daemon is down
/// - `not_installed`  — daemon up, but no Nova compose file yet
/// - `stopped`        — compose file exists, container not running
/// - `initializing`   — container running, dashboard not reachable yet
/// - `running`        — container running and dashboard reachable
///
/// The first failing check wins, so an earlier (worse) state is always
/// reported before a later (better) one.
#[tauri::command]
pub async fn get_app_state() -> String {
    if !docker_installed() {
        return "docker_missing".to_string();
    }
    if !docker_daemon_running().await {
        return "docker_stopped".to_string();
    }
    if !nova_installed() {
        return "not_installed".to_string();
    }
    if container_status().await.is_empty() {
        return "stopped".to_string();
    }
    if !dashboard_reachable().await {
        return "initializing".to_string();
    }
    "running".to_string()
}

/// Search `PATH` for an executable named `binary`.
fn which_in_path(binary: &str) -> Option<PathBuf> {
    let path_var = env::var_os("PATH")?;
    // Windows executables carry an extension (Docker Desktop's CLI ships as
    // `docker.exe`); a bare `docker` file never exists there.
    #[cfg(target_os = "windows")]
    let file_name = format!("{binary}.exe");
    #[cfg(not(target_os = "windows"))]
    let file_name = binary.to_string();
    for dir in env::split_paths(&path_var) {
        let candidate = dir.join(&file_name);
        if candidate.is_file() && is_executable(&candidate) {
            return Some(candidate);
        }
    }
    None
}

/// Best-effort check that `path` points to an executable file.
fn is_executable(path: &Path) -> bool {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        path.metadata()
            .map(|m| m.permissions().mode() & 0o111 != 0)
            .unwrap_or(false)
    }
    #[cfg(not(unix))]
    {
        path.is_file()
    }
}
