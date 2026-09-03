#![deny(clippy::all)]

mod actions;
mod docker;
mod launch;

// Bring every command function into scope so `generate_handler!` can reference
// them by bare name. Each `#[tauri::command]` fn above is `pub`, so the
// per-command helper macros it emits get `#[macro_export]` (hoisted to the
// crate root) — which is what lets the bare-name `generate_handler!` entries
// resolve their `__cmd__*` / `__tauri_command_name_*` macros.
use actions::*;
use docker::*;
use launch::*;

fn main () {
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
      launch_docker,
    ])
    .run(tauri::generate_context!())
    .expect("error while running Nova DSO Tracker");
}
