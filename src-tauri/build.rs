fn main () {
  tauri_build::try_build(
    tauri_build::Attributes::new()
      .app_manifest(
        tauri_build::AppManifest::new().commands(&[
          // docker.rs
          "docker_installed",
          "docker_daemon_running",
          "nova_installed",
          "container_status",
          "dashboard_reachable",
          "get_app_state",
          // actions.rs
          "start_tracker",
          "stop_tracker",
          "pull_image",
          "recreate_tracker",
          "prune_images",
          // launch.rs
          "open_dashboard",
          "open_docker_download",
          "open_url",
          "launch_docker",
          // updates.rs
          "check_launcher_update",
          "check_image_update",
          "skip_image_version",
          // window.rs
          "resize_window",
        ]),
      ),
  )
  .expect("failed to run tauri build");
}
