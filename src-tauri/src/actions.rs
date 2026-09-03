//! Mutating Docker operations exposed as Tauri commands.
//!
//! Unlike `docker.rs` (read-only checks), these actually change system state:
//! they create the Nova compose file, start/stop/recreate the tracker
//! container, pull images, and prune images. Each returns `Ok(())` on success
//! or an `Err(String)` carrying Docker's output so the UI can surface it.
//!
//! Commands are async and use `tokio::process` (matching `docker.rs`) so a
//! slow operation like `docker pull` never blocks the async runtime.

use std::path::PathBuf;

use tokio::process::Command;

/// Built-in `docker-compose.yml` written to `~/nova/` on first start, when
/// none already exists.
const COMPOSE_TEMPLATE: &str = r#"services:
  nova:
    image: mrantonsg/nova-dso-tracker:latest
    container_name: nova-tracker
    ports:
      - "5001:5001"
    volumes:
      - ./instance:/app/instance
    restart: unless-stopped
"#;

/// The image pulled by `pull_image` and referenced by the compose template.
const TRACKER_IMAGE: &str = "mrantonsg/nova-dso-tracker:latest";

/// Path to the Nova compose file: `~/nova/docker-compose.yml`.
fn compose_file_path() -> Result<PathBuf, String> {
    let home = dirs::home_dir()
        .ok_or_else(|| "could not determine home directory".to_string())?;
    Ok(home.join("nova").join("docker-compose.yml"))
}

/// Creates `~/nova/docker-compose.yml` from `COMPOSE_TEMPLATE` if it does not
/// already exist, creating the `~/nova` directory as needed. Returns the path.
fn ensure_compose_file() -> Result<PathBuf, String> {
    let compose_path = compose_file_path()?;
    if !compose_path.exists() {
        if let Some(parent) = compose_path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|e| format!("failed to create {}: {e}", parent.display()))?;
        }
        std::fs::write(&compose_path, COMPOSE_TEMPLATE)
            .map_err(|e| format!("failed to write {}: {e}", compose_path.display()))?;
    }
    Ok(compose_path)
}

/// Runs a plain `docker <args...>` command, returning Docker's output on failure.
async fn run_docker(args: &[&str]) -> Result<(), String> {
    let mut cmd = Command::new("docker");
    cmd.args(args);
    let output = cmd
        .output()
        .await
        .map_err(|e| format!("failed to run docker: {e}"))?;
    if output.status.success() {
        Ok(())
    } else {
        Err(command_error(&output))
    }
}

/// Runs `docker compose -f ~/nova/docker-compose.yml <args...>`.
async fn run_compose(args: &[&str]) -> Result<(), String> {
    let compose_path = compose_file_path()?;
    let mut cmd = Command::new("docker");
    cmd.arg("compose");
    cmd.arg("-f");
    cmd.arg(&compose_path);
    cmd.args(args);
    let output = cmd
        .output()
        .await
        .map_err(|e| format!("failed to run docker compose: {e}"))?;
    if output.status.success() {
        Ok(())
    } else {
        Err(command_error(&output))
    }
}

/// Builds a human-readable error from a failed command's output, preferring
/// stderr and falling back to stdout, then the exit status.
///
/// `pub(crate)` so sibling modules (e.g. `launch.rs`) can reuse the same
/// error formatting.
pub(crate) fn command_error(output: &std::process::Output) -> String {
    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);
    if !stderr.trim().is_empty() {
        stderr.trim().to_string()
    } else if !stdout.trim().is_empty() {
        stdout.trim().to_string()
    } else {
        format!("docker command exited with status {}", output.status)
    }
}

/// Creates the Nova compose file (if missing), then starts the tracker:
/// `docker compose -f ~/nova/docker-compose.yml up -d`.
#[tauri::command]
pub async fn start_tracker() -> Result<(), String> {
    ensure_compose_file()?;
    run_compose(&["up", "-d"]).await
}

/// Stops the tracker: `docker compose -f ~/nova/docker-compose.yml stop`.
#[tauri::command]
pub async fn stop_tracker() -> Result<(), String> {
    run_compose(&["stop"]).await
}

/// Pulls the latest tracker image: `docker pull mrantonsg/nova-dso-tracker:latest`.
#[tauri::command]
pub async fn pull_image() -> Result<(), String> {
    run_docker(&["pull", TRACKER_IMAGE]).await
}

/// Force-recreates the tracker: `docker compose -f ... up -d --force-recreate`.
#[tauri::command]
pub async fn recreate_tracker() -> Result<(), String> {
    run_compose(&["up", "-d", "--force-recreate"]).await
}

/// Removes dangling images: `docker image prune -f`.
#[tauri::command]
pub async fn prune_images() -> Result<(), String> {
    run_docker(&["image", "prune", "-f"]).await
}
