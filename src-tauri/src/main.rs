#![deny(clippy::all)]

mod actions;
mod docker;
mod launch;
mod updates;
mod window;

// Bring every command function into scope so `generate_handler!` can reference
// them by bare name. Each `#[tauri::command]` fn above is `pub`, so the
// per-command helper macros it emits get `#[macro_export]` (hoisted to the
// crate root) — which is what lets the bare-name `generate_handler!` entries
// resolve their `__cmd__*` / `__tauri_command_name_*` macros.
use actions::*;
use docker::*;
use launch::*;
use updates::*;
use window::*;

/// Augments the process's `PATH` with common Homebrew/Docker install
/// locations before any docker-invoking command runs.
///
/// A Finder-launched `.app` inherits a minimal default `PATH` (unlike a
/// terminal shell), so it lacks `/usr/local/bin` and `/opt/homebrew/bin` —
/// which is where Docker Desktop's `docker` CLI symlink lives. Every
/// `Command::new("docker")` / `Command::new("open")` call across
/// `docker.rs`, `actions.rs`, `launch.rs`, and `updates.rs` inherits this
/// process's environment, so fixing `PATH` once here, before Tauri starts,
/// covers all of them. Mirrors the Python launcher's startup PATH fix in
/// `nova_manager.py` (and `docker_ops.py`'s per-call version).
fn augment_docker_path() {
  #[cfg(target_os = "macos")]
  let extra_dirs: &[&str] = &["/usr/local/bin", "/opt/homebrew/bin"];
  #[cfg(all(unix, not(target_os = "macos")))]
  let extra_dirs: &[&str] = &["/usr/local/bin", "/snap/bin"];
  #[cfg(not(unix))]
  let extra_dirs: &[&str] = &[];

  if extra_dirs.is_empty() {
    return;
  }

  let path_var = std::env::var_os("PATH").unwrap_or_default();
  let mut dirs: Vec<std::path::PathBuf> = std::env::split_paths(&path_var).collect();
  let mut changed = false;
  for extra in extra_dirs {
    let extra_path = std::path::PathBuf::from(extra);
    if !dirs.contains(&extra_path) {
      dirs.push(extra_path);
      changed = true;
    }
  }
  if changed {
    if let Ok(joined) = std::env::join_paths(dirs) {
      // Safety: called first thing in `main`, before Tauri (or anything
      // else) has spawned other threads that might read/write `PATH`
      // concurrently.
      unsafe {
        std::env::set_var("PATH", joined);
      }
    }
  }
}

fn main () {
  augment_docker_path();

  tauri::Builder::default()
    .plugin(tauri_plugin_opener::init())
    .invoke_handler(tauri::generate_handler![
      // Read-only Docker / Nova status checks
      docker_installed,
      docker_daemon_running,
      nova_installed,
      container_status,
      dashboard_reachable,
      get_app_state,
      // Mutating Docker operations
      start_tracker,
      stop_tracker,
      pull_image,
      recreate_tracker,
      prune_images,
      // Opening external resources
      open_dashboard,
      open_docker_download,
      open_url,
      launch_docker,
      // Update checks
      check_launcher_update,
      check_image_update,
      skip_image_version,
      // Window control
      resize_window,
    ])
    .run(tauri::generate_context!())
    .expect("error while running Nova DSO Tracker");
}
