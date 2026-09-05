//! Programmatic resizing of the main window.
//!
//! The window stays `resizable: false` in tauri.conf.json (the user never
//! drags it) — this command is the app growing/shrinking itself in response
//! to content, mirroring the CustomTkinter original's auto-expand-for-log-
//! viewer behavior.

use tauri::{LogicalSize, WebviewWindow};

/// Resizes the main window to `height` logical pixels, keeping the
/// configured width (480, from tauri.conf.json) fixed.
#[tauri::command]
pub fn resize_window(window: WebviewWindow, height: u32) -> Result<(), String> {
    window
        .set_size(LogicalSize::new(480.0, height as f64))
        .map_err(|e| format!("failed to resize window: {e}"))
}
