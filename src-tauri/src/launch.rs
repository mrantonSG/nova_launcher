//! Commands for opening external resources in the OS default handler.
//!
//! URLs are handed to the system browser via `tauri-plugin-opener`; launching
//! Docker is handled per-platform in `launch_docker` (see its doc comment
//! and the per-OS helpers below it), and is best-effort and fails
//! gracefully everywhere.

use tauri_plugin_opener::open_url as plugin_open_url;

use crate::actions::command_error;

/// Opens the local Nova dashboard in the default browser: `http://localhost:5001`.
#[tauri::command]
pub fn open_dashboard() -> Result<(), String> {
    plugin_open_url("http://localhost:5001", None::<&str>)
        .map_err(|e| format!("failed to open the dashboard: {e}"))
}

/// Opens Docker's download page in the default browser.
#[tauri::command]
pub fn open_docker_download() -> Result<(), String> {
    plugin_open_url(
        "https://www.docker.com/products/docker-desktop/",
        None::<&str>,
    )
    .map_err(|e| format!("failed to open the Docker download page: {e}"))
}

/// Opens an arbitrary URL in the default browser (e.g. a GitHub release
/// page). Unlike `open_dashboard`/`open_docker_download`, the target isn't
/// hardcoded, so it comes from the caller.
#[tauri::command]
pub fn open_url(url: String) -> Result<(), String> {
    plugin_open_url(&url, None::<&str>).map_err(|e| format!("failed to open URL: {e}"))
}

/// Best-effort launch of Docker, dispatched to a per-platform
/// implementation below. Each implementation fails gracefully (returning a
/// descriptive error) rather than panicking when Docker isn't installed or
/// can't be started.
#[tauri::command]
pub async fn launch_docker() -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        launch_docker_macos().await
    }
    #[cfg(target_os = "windows")]
    {
        launch_docker_windows().await
    }
    #[cfg(target_os = "linux")]
    {
        launch_docker_linux().await
    }
    #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
    {
        Err("launching Docker isn't supported on this platform".to_string())
    }
}

/// macOS: ask Launch Services to start the installed Docker Desktop app.
#[cfg(target_os = "macos")]
async fn launch_docker_macos() -> Result<(), String> {
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

/// Windows: there's no `open -a`-style app launcher, so start Docker
/// Desktop's executable directly from its default install location. This
/// path is not user-configurable at install time in the normal installer
/// flow, but a user can still choose a custom location manually, so we
/// check for the file rather than assuming it's there.
///
/// UNVERIFIED: written by reasoning about the platform, not tested on a
/// real Windows machine.
#[cfg(target_os = "windows")]
async fn launch_docker_windows() -> Result<(), String> {
    let program_files =
        std::env::var("ProgramFiles").unwrap_or_else(|_| "C:\\Program Files".to_string());
    let exe = std::path::Path::new(&program_files)
        .join("Docker")
        .join("Docker")
        .join("Docker Desktop.exe");
    if !exe.is_file() {
        return Err(format!(
            "Docker Desktop wasn't found at \"{}\". If you installed it to a different location, please start it manually from there.",
            exe.display()
        ));
    }
    // Spawn and don't wait: unlike macOS's `open`, which just enqueues an
    // open request and returns immediately, launching the executable
    // directly starts Docker Desktop as our child process. Awaiting its
    // `.output()` would block until Docker Desktop itself exits, so we
    // only confirm the spawn succeeded and let it run independently.
    tokio::process::Command::new(&exe)
        .spawn()
        .map(|_child| ())
        .map_err(|e| format!("failed to launch Docker Desktop: {e}"))
}

/// Linux: there's no single "Docker Desktop" equivalent across distros, and
/// starting the daemon usually needs elevated privileges that a GUI app
/// can't silently assume. This is a judgment call — see the PR description
/// for the reasoning — implemented as a layered best-effort:
///
///  1. Docker Desktop for Linux (where installed) runs its backend as a
///     per-user systemd unit, `docker-desktop`, which needs no elevated
///     privileges. Try that first.
///  2. Plain Docker Engine (`docker-ce`, the more common Linux install)
///     runs `dockerd` as a root-owned system service, `docker`. Starting
///     it needs a privilege prompt; `pkexec` is the standard PolicyKit
///     graphical-auth helper present on most desktop distros (GNOME, KDE,
///     etc.), so we shell out through it rather than `sudo` (which needs a
///     TTY and has no GUI prompt).
///  3. If neither is available (e.g. `pkexec` missing on a minimal/non-GUI
///     distro, or systemd absent entirely), fall back to telling the user
///     what to run themselves rather than failing silently.
///
/// UNVERIFIED: written by reasoning about the platform, not tested on a
/// real Linux machine. Please validate on both a Docker-Desktop-for-Linux
/// setup and a plain docker-ce + systemd setup before relying on this.
#[cfg(target_os = "linux")]
async fn launch_docker_linux() -> Result<(), String> {
    if let Ok(output) = tokio::process::Command::new("systemctl")
        .args(["--user", "start", "docker-desktop"])
        .output()
        .await
    {
        if output.status.success() {
            return Ok(());
        }
    }

    if command_exists_in_path("pkexec") {
        let output = tokio::process::Command::new("pkexec")
            .args(["systemctl", "start", "docker"])
            .output()
            .await
            .map_err(|e| format!("failed to run `pkexec`: {e}"))?;
        return if output.status.success() {
            Ok(())
        } else {
            Err(command_error(&output))
        };
    }

    Err("Docker couldn't be started automatically on Linux. Please start it manually: run \
         `sudo systemctl start docker` in a terminal, or launch Docker Desktop from your \
         application menu if you have it installed."
        .to_string())
}

/// Best-effort check for whether `name` resolves on `PATH`, without
/// actually running it (so a merely-present-but-unrelated `--version` flag
/// can't cause surprises).
#[cfg(target_os = "linux")]
fn command_exists_in_path(name: &str) -> bool {
    std::env::var_os("PATH")
        .map(|paths| std::env::split_paths(&paths).any(|dir| dir.join(name).is_file()))
        .unwrap_or(false)
}
