# -*- coding: utf-8 -*-
"""
Nova DSO Tracker Launcher - Main Application

A cross-platform GUI launcher for Nova DSO Tracker that manages Docker containers.
Migrated to CustomTkinter with Nova DSO Tracker design system.
"""

import customtkinter as ctk
import tkinter as tk
import subprocess
import ssl
import threading
import time
import webbrowser
import urllib.request
import json
import os
import sys
import certifi

# SSL context for HTTPS requests (uses certifi's bundled certificates)
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# Helper for PyInstaller resource paths (needed before theme load)
def _resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except (AttributeError, Exception):
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# Set CustomTkinter appearance before any widget creation
ctk.set_appearance_mode("light")
ctk.set_default_color_theme(_resource_path("assets/nova_theme.json"))

# Import from refactored modules
from config import (
    APP_NAME,
    APP_VERSION,
    DOCKER_CONTAINER_NAME,
    DOCKER_IMAGE,
    DOCKER_TAG,
    DOCKER_IMAGE_FULL,
    PORT,
    DOCKER_DOWNLOAD_URL,
    GITHUB_RELEASES_API,
    NOVA_DIR,
    INSTANCE_DIR,
    COMPOSE_FILE,
    COMPOSE_TEMPLATE,
    DOCKER_CMD_TIMEOUT,
    DOCKER_INFO_TIMEOUT,
    CONTAINER_START_POLL_COUNT,
    DOCKER_START_POLL_COUNT,
    MONITOR_INTERVAL,
    UPDATE_BANNER_DISPLAY_TIME,
)
from docker_ops import (
    run_command,
    is_docker_installed,
    is_docker_running,
    is_nova_installed,
    is_container_running,
    create_compose_file,
    pull_image,
    start_container,
    stop_container,
    recreate_container,
    prune_images,
    get_container_image_digest,
    get_local_image_digest,
    check_dockerhub_version,
    load_launcher_prefs,
    save_launcher_prefs,
    get_skipped_digest,
    set_skipped_digest,
)
from utils import (
    check_web_ready,
    version_newer,
    open_dashboard as open_dashboard_url,
)

# --- Nova Design System Colors (Light Mode Only) ---
NOVA_TEAL = "#83b4c5"
NOVA_TEAL_HOVER = "#6a9eb0"

DANGER = "#a04040"
DANGER_BG = "#faf6f6"
DANGER_HOVER = "#f5e8e8"
DANGER_BORDER = "#e8c8c8"

GHOST_BG = "transparent"
GHOST_HOVER = "#f7f5f2"
GHOST_TEXT = "#4a4a4a"
GHOST_BORDER = "#d0cdc8"

STATUS_RUNNING = "#83b4c5"
STATUS_STOPPED = "#888888"
STATUS_ERROR = "#a04040"

# Log viewer memory limit
MAX_LOG_LINES = 500


class NovaManagerApp:
    def __init__(self, root):
        self.root = root

        # --- FIX ENV PATH (for legacy compatibility) ---
        if sys.platform == "darwin":
            os.environ["PATH"] += os.pathsep + "/usr/local/bin" + os.pathsep + "/opt/homebrew/bin"
        elif sys.platform == "linux":
            os.environ["PATH"] += os.pathsep + "/usr/local/bin" + os.pathsep + "/snap/bin"

        self.root.title("Nova DSO Tracker Launcher")
        self.root.geometry("500x580")
        self.root.resizable(False, False)

        # Graceful shutdown handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Ensure NOVA_DIR exists
        if not os.path.exists(NOVA_DIR):
            try:
                os.makedirs(NOVA_DIR)
            except Exception as e:
                self._show_error_dialog("Error", f"Cannot create install directory:\n{NOVA_DIR}\n\n{e}")

        self.is_processing = False
        self.just_installed = False
        self.stop_event = threading.Event()
        self.log_lines = []
        self.pending_update_digest = None
        self._update_check_done = False  # Track if Docker Hub check was performed this session

        self.setup_ui()

        # Start Background Monitor
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

        # Check for launcher updates in background
        threading.Thread(target=self._check_launcher_update, daemon=True).start()

    def _on_close(self):
        """Graceful shutdown: stop monitor thread and optionally stop the container."""
        self.stop_event.set()
        self.root.destroy()

    def setup_ui(self):
        # --- Header ---
        header = ctk.CTkFrame(self.root, fg_color="transparent")
        header.pack(fill=tk.X, padx=30, pady=(30, 20))

        # Nova Wordmark - text-based logo (no image file needed)
        wordmark_frame = ctk.CTkFrame(header, fg_color="transparent")
        wordmark_frame.pack(side=tk.LEFT, padx=(0, 15))

        # "Nova" in bold teal
        lbl_nova = ctk.CTkLabel(
            wordmark_frame,
            text="Nova",
            font=("DM Sans", 22, "bold"),
            text_color=NOVA_TEAL
        )
        lbl_nova.pack(side=tk.LEFT)

        # "DSO Tracker" in regular dark
        lbl_tracker = ctk.CTkLabel(
            wordmark_frame,
            text=" DSO Tracker",
            font=("DM Sans", 22),
            text_color="#141414"
        )
        lbl_tracker.pack(side=tk.LEFT)

        # Title Block
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side=tk.LEFT, anchor="center")
        ctk.CTkLabel(
            title_frame,
            text=APP_NAME,
            font=("DM Sans", 20, "bold")
        ).pack(anchor="w")
        self.lbl_status_header = ctk.CTkLabel(
            title_frame,
            text="Initializing...",
            font=("DM Sans", 13)
        )
        self.lbl_status_header.pack(anchor="w")

        # Status Dot (using label with unicode)
        self.lbl_dot = ctk.CTkLabel(
            header,
            text="●",
            font=("DM Sans", 14),
            text_color=STATUS_STOPPED
        )
        self.lbl_dot.pack(side=tk.RIGHT)

        # Divider
        divider = ctk.CTkFrame(self.root, height=1, fg_color="#e5e2dc")
        divider.pack(fill=tk.X, pady=(0, 10))

        # --- Content Area ---
        self.content_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=20)

        # Center Status Text
        self.lbl_center_info = ctk.CTkLabel(
            self.content_frame,
            text="Checking status...",
            font=("DM Sans", 12),
            wraplength=400,
            justify="center"
        )
        self.lbl_center_info.pack(pady=(20, 5))

        # Progress Bar
        self.progress = ctk.CTkProgressBar(self.content_frame, mode="indeterminate", width=200)
        self.progress.set(0)

        # Buttons Row
        self.btn_row = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.btn_row.pack(pady=15)

        self.btn_main = ctk.CTkButton(
            self.btn_row,
            text="Loading...",
            command=self.on_main_action,
            width=140,
            height=38,
            font=("DM Sans", 13, "bold")
        )
        self.btn_main.pack(side=tk.LEFT, padx=10)

        self.btn_stop = self._create_danger_button(
            self.btn_row,
            "Stop Tracker",
            self.stop_nova,
            width=140,
            height=38
        )

        # Version / image info label
        self.lbl_version = ctk.CTkLabel(
            self.content_frame,
            text="",
            font=("DM Sans", 10)
        )
        self.lbl_version.pack(pady=(5, 0))

        # --- Log Viewer ---
        log_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(5, 5))

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.pack(fill=tk.X)
        ctk.CTkLabel(
            log_header,
            text="Logs",
            font=("DM Sans", 10, "bold")
        ).pack(side=tk.LEFT)

        self.log_toggle_var = tk.BooleanVar(value=False)
        self.log_toggle_btn = ctk.CTkLabel(
            log_header,
            text="Show",
            font=("DM Sans", 10),
            text_color=NOVA_TEAL,
            cursor="hand2"
        )
        self.log_toggle_btn.pack(side=tk.RIGHT)
        self.log_toggle_btn.bind("<Button-1>", lambda e: self._toggle_logs())

        self.log_text = ctk.CTkTextbox(
            log_frame,
            height=10,
            font=("Courier New", 10),
            state="disabled",
            wrap="word"
        )
        # Start hidden
        self.log_text.pack_forget()

        # --- Footer ---
        footer = ctk.CTkFrame(self.root, fg_color="transparent")
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 15))

        # Update Link
        self.lbl_update = ctk.CTkLabel(
            footer,
            text="↻ Check for Updates",
            font=("DM Sans", 11),
            cursor="hand2"
        )
        self.lbl_update.pack(side=tk.BOTTOM, pady=(10, 0))
        self.lbl_update.bind("<Button-1>", lambda e: self.check_update())

        # Launcher version label
        self.lbl_launcher_ver = ctk.CTkLabel(
            footer,
            text=f"Launcher v{APP_VERSION}",
            font=("DM Sans", 9),
            text_color="#888888"
        )
        self.lbl_launcher_ver.pack(side=tk.BOTTOM)

        # Launcher update banner (hidden by default)
        self.update_banner = ctk.CTkFrame(footer, fg_color="#E8F5E9")
        self.lbl_update_banner = ctk.CTkLabel(
            self.update_banner,
            text="",
            font=("DM Sans", 10),
            text_color="#2E7D32",
            cursor="hand2"
        )
        self.lbl_update_banner.pack(padx=10, pady=5)

    def _create_danger_button(self, parent, text, command, width=140, height=38):
        """Create a danger/stop button with Nova styling."""
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=height,
            font=("DM Sans", 13, "bold"),
            fg_color=DANGER_BG,
            hover_color=DANGER_HOVER,
            text_color=DANGER,
            border_width=1,
            border_color=DANGER_BORDER
        )

    def _create_ghost_button(self, parent, text, command, width=110, height=38):
        """Create a ghost/secondary button with Nova styling."""
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=height,
            font=("DM Sans", 12),
            fg_color="transparent",
            hover_color=GHOST_HOVER,
            text_color=GHOST_TEXT,
            border_width=1,
            border_color=GHOST_BORDER
        )

    def _create_primary_button(self, parent, text, command, width=140, height=38):
        """Create a primary action button with Nova teal styling."""
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=height,
            font=("DM Sans", 13, "bold"),
            fg_color=NOVA_TEAL,
            hover_color=NOVA_TEAL_HOVER,
            text_color="#ffffff",
            border_width=0
        )

    def _toggle_logs(self):
        if self.log_toggle_var.get():
            self.log_text.pack_forget()
            self.log_toggle_btn.configure(text="Show")
            self.log_toggle_var.set(False)
        else:
            self.log_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
            self.log_toggle_btn.configure(text="Hide")
            self.log_toggle_var.set(True)

    def _append_log(self, text):
        """Thread-safe append to the log viewer with line limit."""
        def _update():
            self.log_text.configure(state="normal")
            timestamp = time.strftime("%H:%M:%S")
            self.log_text.insert("end", f"[{timestamp}] {text}\n")

            # Enforce max line limit
            line_count = int(self.log_text.index("end-1c").split(".")[0])
            if line_count > MAX_LOG_LINES:
                lines_to_delete = line_count - MAX_LOG_LINES
                self.log_text.delete("1.0", f"{lines_to_delete + 1}.0")

            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(0, _update)

    # --- UI Helpers ---

    def set_loading(self, is_loading, message="Processing..."):
        self.is_processing = is_loading
        if is_loading:
            self.lbl_center_info.configure(text=message)
            self.progress.pack(after=self.lbl_center_info, pady=(10, 15))
            self.progress.start()
            self.btn_main.configure(state="disabled")
            self.btn_stop.configure(state="disabled")
            self.lbl_update.unbind("<Button-1>")
            self.lbl_update.configure(text_color="#AAAAAA", cursor="")
        else:
            self.progress.stop()
            self.progress.pack_forget()
            self.lbl_update.bind("<Button-1>", lambda e: self.check_update())
            self.lbl_update.configure(
                text_color=NOVA_TEAL,
                cursor="hand2"
            )
            self.lbl_center_info.configure(text="")

    def run_command_legacy(self, command, timeout=DOCKER_CMD_TIMEOUT):
        """Legacy wrapper for run_command that logs output. Returns (stdout, stderr, returncode)."""
        self._append_log(f"$ {command}")

        # Parse shell command into list for secure execution
        args = command.split()

        stdout, stderr, rc = run_command(args, timeout=timeout, cwd=NOVA_DIR)

        if stdout:
            self._append_log(stdout)
        if stderr:
            self._append_log(f"[stderr] {stderr}")

        return stdout, stderr, rc

    def check_port_available(self):
        """Check if the configured port is available before starting."""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("127.0.0.1", PORT))
                if result == 0:
                    # Port is in use - check if it's our container
                    is_running, _ = is_container_running()
                    if is_running:
                        return True  # Our container is using it, that's fine
                    return False  # Something else is using the port
                return True  # Port is free
        except Exception:
            return True  # If check fails, proceed anyway

    def monitor_loop(self):
        while not self.stop_event.is_set():
            if not self.is_processing:
                self.check_state()
            time.sleep(MONITOR_INTERVAL)

    def check_state(self):
        # 1. Docker installed?
        if not is_docker_installed():
            self.update_ui("docker_missing")
            return

        # 2. Docker daemon running?
        is_running, status = is_docker_running()
        if not is_running:
            if status == "missing":
                self.update_ui("docker_missing")
            else:
                self.update_ui("docker_stopped")
            return

        # 3. Check for Docker Hub updates (non-blocking, after daemon check)
        # Only check ONCE per session, before container is launched
        if not self._update_check_done:
            self._update_check_done = True
            threading.Thread(target=self._check_image_update_background, daemon=True).start()

        # 4. Nova installed?
        if not is_nova_installed():
            self.update_ui("not_installed")
            return

        # 5. Container running?
        is_running, status_str = is_container_running()

        if is_running:
            if check_web_ready():
                self.update_ui("running")
            else:
                self.update_ui("initializing")
        else:
            self.update_ui("stopped")

    def _check_image_update_background(self):
        """Background check for Docker Hub image updates."""
        try:
            update_available, remote_digest, error = check_dockerhub_version()

            if error:
                self._append_log(f"[info] Docker Hub check: {error}")
                return

            if update_available and remote_digest:
                # Check if user has skipped this version
                skipped = get_skipped_digest()
                if skipped and remote_digest == skipped:
                    self._append_log("[info] Update available but user skipped this version")
                    return

                # Store the pending digest and prompt user
                self.pending_update_digest = remote_digest
                # Use default argument to capture value, not reference
                self.root.after(0, lambda d=remote_digest: self._prompt_update_dialog(d))
        except Exception as e:
            self._append_log(f"[warn] Docker Hub check failed: {e}")

    def _show_error_dialog(self, title, message):
        """Show an error dialog using CTkToplevel."""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title(title)
        dialog.geometry("400x150")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.geometry(f"+{self.root.winfo_x() + 50}+{self.root.winfo_y() + 100}")

        ctk.CTkLabel(
            dialog,
            text=message,
            font=("DM Sans", 12),
            wraplength=350,
            justify="center"
        ).pack(pady=30)

        ctk.CTkButton(
            dialog,
            text="OK",
            command=dialog.destroy,
            width=100
        ).pack()

    def _show_info_dialog(self, title: str, message: str, digest: str = None):
        """Show an info dialog using CTkToplevel with optional digest display."""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title(title)
        dialog.geometry("420x200" if digest else "400x150")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.geometry(f"+{self.root.winfo_x() + 40}+{self.root.winfo_y() + 100}")

        # Message
        ctk.CTkLabel(
            dialog,
            text=message,
            font=("DM Sans", 13),
            wraplength=350,
            justify="center"
        ).pack(pady=(30, 10) if digest else 30)

        # Show digest if provided
        if digest:
            # Extract short digest for display
            short_digest = digest.replace("sha256:", "")[:12]
            ctk.CTkLabel(
                dialog,
                text=f"Image digest: {short_digest}",
                font=("DM Sans", 10),
                text_color="#666666"
            ).pack(pady=(0, 20))

        # OK button
        ctk.CTkButton(
            dialog,
            text="OK",
            command=dialog.destroy,
            width=100,
            font=("DM Sans", 12)
        ).pack(pady=10)

    def _prompt_update_dialog(self, remote_digest: str, on_update_callback=None):
        """Show a dialog prompting the user to update.

        Args:
            remote_digest: The digest of the available update
            on_update_callback: Optional callback for Update Now button. If None, uses default behavior.
        """
        # Don't prompt if we're processing something else
        if self.is_processing:
            return

        # Create a custom dialog
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Update Available")
        dialog.geometry("420x200")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.geometry(f"+{self.root.winfo_x() + 40}+{self.root.winfo_y() + 100}")

        # Message
        ctk.CTkLabel(
            dialog,
            text="A newer version of Nova DSO Tracker is available!",
            font=("DM Sans", 14, "bold")
        ).pack(pady=(25, 10))

        ctk.CTkLabel(
            dialog,
            text=f"Image: {DOCKER_IMAGE}:{DOCKER_TAG}",
            font=("DM Sans", 11)
        ).pack(pady=(0, 25))

        # Buttons frame
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)

        def on_update():
            dialog.destroy()
            if on_update_callback:
                on_update_callback()
            else:
                self._perform_image_update()

        def on_skip():
            dialog.destroy()
            # Clear pending so we don't prompt again this session
            self.pending_update_digest = None

        def on_skip_version():
            set_skipped_digest(remote_digest)
            self.pending_update_digest = None
            dialog.destroy()

        self._create_primary_button(btn_frame, "Update Now", on_update, width=120).pack(side=tk.LEFT, padx=5)
        self._create_ghost_button(btn_frame, "Skip", on_skip, width=80).pack(side=tk.LEFT, padx=5)
        self._create_ghost_button(btn_frame, "Skip Version", on_skip_version, width=110).pack(side=tk.LEFT, padx=5)

    def _perform_image_update(self):
        """Pull the latest image and recreate the container (auto-starts after update)."""
        self._do_image_update(auto_start=True)

    def _perform_manual_update(self):
        """Pull the latest image and recreate the container (does NOT auto-start)."""
        self._do_image_update(auto_start=False)

    def _do_image_update(self, auto_start: bool = True):
        """Pull the latest image and recreate the container.

        Args:
            auto_start: If True, calls check_state after update to potentially start container.
                       If False, just refreshes UI state without auto-starting.
        """
        self.set_loading(True, "Downloading update...")

        def _update_thread():
            self._append_log("Pulling latest image...")

            # Store the digest before pulling to save as skipped after success
            digest_to_skip = self.pending_update_digest

            # Pull the image
            success, msg = pull_image()
            if not success:
                self.root.after(0, lambda: self._show_error_dialog("Update Failed", f"Failed to pull image:\n{msg}"))
                self.root.after(0, lambda: self.set_loading(False))
                self.pending_update_digest = None
                return

            # Save the new digest as skipped so we don't prompt again for this version
            if digest_to_skip:
                set_skipped_digest(digest_to_skip)

            # Stop and recreate container
            self._append_log("Recreating container...")
            stop_container()

            success, msg = recreate_container()
            if not success:
                self.root.after(0, lambda: self._show_error_dialog("Update Failed", f"Failed to recreate container:\n{msg}"))

            # Cleanup old images
            prune_images()

            # Clear pending
            self.pending_update_digest = None

            # Show success message for manual update
            self.root.after(0, lambda: self.lbl_update.configure(
                text="↻ Update Complete",
                text_color="#4CD964"
            ))

            self.root.after(0, lambda: self.set_loading(False))

            if auto_start:
                # Auto-start: check state which may start container
                self.root.after(200, self.check_state)
            else:
                # Manual: just refresh UI, don't auto-start
                self.root.after(200, self._refresh_ui_after_update)

            # Reset button text after delay
            def reset_button():
                self.lbl_update.configure(text="↻ Check for Updates", text_color=NOVA_TEAL)
            self.root.after(3000, reset_button)

        threading.Thread(target=_update_thread, daemon=True).start()

    def _refresh_ui_after_update(self):
        """Refresh UI state after manual update without auto-starting container."""
        self.check_state()

    def update_ui(self, state):
        self.root.after(0, lambda: self._apply_ui_state(state))

    def _apply_ui_state(self, state):
        if self.is_processing:
            return

        self.btn_main.configure(state="normal")
        self.btn_stop.configure(state="normal")

        if state == "docker_missing":
            self.set_status("Docker Missing", STATUS_ERROR,
                            "Docker Desktop is required to run Nova.\n\n"
                            "Click below to download it. Once installed,\n"
                            "open Docker Desktop and return here.")
            self.btn_main.configure(text="Download Docker", command=self.open_docker)
            self._style_button_primary(self.btn_main)
            self.btn_stop.pack_forget()
            self.lbl_version.configure(text="")

        elif state == "docker_stopped":
            self.set_status("Docker Not Running", "#FF9500",
                            "Please open Docker Desktop to continue.")
            self.btn_main.configure(text="Launch Docker", command=self.launch_docker_app)
            self._style_button_primary(self.btn_main)
            self.btn_stop.pack_forget()
            self.lbl_version.configure(text="")

        elif state == "not_installed":
            self.set_status("Not Installed", STATUS_STOPPED,
                            f"Install location: {NOVA_DIR}")
            self.btn_main.configure(text="Install Nova", command=self.install_nova)
            self._style_button_primary(self.btn_main)
            self.btn_stop.pack_forget()
            self.lbl_version.configure(text="")

        elif state == "stopped":
            self.set_status("Service Stopped", "#FF9500",
                            "Service is stopped.")
            self.btn_main.configure(text="Start Tracker", command=self.start_nova)
            self._style_button_primary(self.btn_main)
            self.btn_stop.pack_forget()
            self._update_version_label()

        elif state == "initializing":
            if self.just_installed:
                msg = "First-time setup: Web UI may take ~2 mins to initialize.\nSubsequent runs will be real-time."
                self.set_status("Initializing...", "#FF9500", msg)
            else:
                self.set_status("Initializing...", "#FF9500", "Starting up... (this may take a minute)")
            self.btn_main.configure(text="Open Dashboard", command=self.open_dashboard)
            self._style_button_primary(self.btn_main)
            self.btn_stop.pack(side=tk.LEFT, padx=10)
            self._update_version_label()

        elif state == "running":
            self.just_installed = False
            self.set_status("Nova Tracker is Active", STATUS_RUNNING, "")
            self.lbl_center_info.configure(text="")
            self.btn_main.configure(text="Open Dashboard", command=self.open_dashboard)
            self._style_button_primary(self.btn_main)
            self.btn_stop.pack(side=tk.LEFT, padx=10)
            self._update_version_label()

    def _style_button_primary(self, btn):
        """Apply primary button styling."""
        btn.configure(
            fg_color=NOVA_TEAL,
            hover_color=NOVA_TEAL_HOVER,
            text_color="#ffffff",
            border_width=0
        )

    def _update_version_label(self):
        """Show the running image digest in the version label."""
        def _fetch():
            digest = get_container_image_digest()
            if digest:
                self.root.after(0, lambda: self.lbl_version.configure(
                    text=f"Image: {DOCKER_IMAGE}:{DOCKER_TAG}  •  {digest}"))
            else:
                self.root.after(0, lambda: self.lbl_version.configure(text=""))
        threading.Thread(target=_fetch, daemon=True).start()

    def set_status(self, header, dot_color, center):
        self.lbl_status_header.configure(text=header)
        self.lbl_dot.configure(text_color=dot_color)
        self.lbl_center_info.configure(text=center)

    # --- Actions ---

    def on_main_action(self):
        pass

    def install_nova(self):
        self.just_installed = True
        self.set_loading(True, "Initializing installation...")

        try:
            os.makedirs(NOVA_DIR, exist_ok=True)
        except Exception as e:
            self._append_log(f"[error] Cannot create directory {NOVA_DIR}: {e}")
            self._show_error_dialog("Installation Error",
                                    f"Cannot create install directory:\n{NOVA_DIR}\n\n{e}")
            self.set_loading(False)
            return

        # Create compose file
        if not create_compose_file():
            self._append_log(f"[error] Failed to create docker-compose.yml")
            self._show_error_dialog("Installation Error",
                                    f"Failed to create docker-compose.yml in:\n{NOVA_DIR}")
            self.set_loading(False)
            return

        self._append_log(f"Created docker-compose.yml at {COMPOSE_FILE}")

        threading.Thread(target=self._perform_install_sequence).start()

    def _perform_install_sequence(self):
        self.root.after(0, lambda: self.lbl_center_info.configure(text="Downloading images... (this may take 2-3 mins)"))

        # Pull image
        success, msg = pull_image()
        if not success:
            self.root.after(0, lambda: self._show_error_dialog("Pull Failed", f"Failed to pull Docker image.\n\n{msg}"))
            self.root.after(0, lambda: self.set_loading(False))
            return

        msg = "First-time setup: Web UI may take ~2 mins to initialize.\nSubsequent runs will be real-time."
        self.root.after(0, lambda: self.lbl_center_info.configure(text=msg))

        # Start container
        success, msg = start_container()
        if not success:
            self.root.after(0, lambda: self._show_error_dialog("Start Failed", f"Failed to start container.\n\n{msg}"))
            self.root.after(0, lambda: self.set_loading(False))
            return

        self.root.after(0, lambda: self.set_loading(False))
        self.root.after(200, self.check_state)

    def start_nova(self):
        # Port conflict check
        if not self.check_port_available():
            self._show_error_dialog("Port Conflict",
                                    f"Port {PORT} is already in use by another application.\n\n"
                                    f"Please free port {PORT} and try again.")
            self._append_log(f"[warn] Port {PORT} is in use by another process")
            return
        self.set_loading(True, "Starting service...")
        threading.Thread(target=self._run_docker_start).start()

    def _run_docker_start(self):
        success, msg = start_container()
        if not success:
            self._append_log(f"[warn] Failed to start: {msg}")
        time.sleep(2)
        self.root.after(0, lambda: self.set_loading(False))
        self.check_state()

    def stop_nova(self):
        self.set_loading(True, "Stopping service...")
        threading.Thread(target=self._run_docker_stop).start()

    def _run_docker_stop(self):
        success, msg = stop_container()
        if not success:
            self._append_log(f"[warn] Failed to stop: {msg}")
        time.sleep(2)
        self.root.after(0, lambda: self.set_loading(False))
        self.check_state()

    def open_dashboard(self):
        open_dashboard_url()

    def open_docker(self):
        webbrowser.open(DOCKER_DOWNLOAD_URL)

    def launch_docker_app(self):
        # Don't try to launch if Docker isn't installed at all
        if not is_docker_installed():
            self._show_error_dialog("Docker Not Found",
                                    "Docker is not installed on this system.\n\n"
                                    "Please install Docker first.")
            self.open_docker()
            return

        self.set_loading(True, "Launching Docker...")

        def _launch_thread():
            launched = False
            try:
                if sys.platform == "darwin":
                    subprocess.run(["open", "-a", "Docker"])
                    launched = True
                elif sys.platform == "win32":
                    win_path = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"
                    if os.path.exists(win_path):
                        os.startfile(win_path)
                        launched = True
                    else:
                        subprocess.run(["start", "docker"], shell=True)
                        launched = True
                elif sys.platform == "linux":
                    result = subprocess.run(["systemctl", "start", "docker"],
                                            capture_output=True, text=True)
                    if result.returncode == 0:
                        launched = True
                    else:
                        self._append_log(f"[error] systemctl start docker failed: {result.stderr.strip()}")
            except Exception as e:
                self._append_log(f"[error] Docker launch failed: {e}")

            if not launched:
                self.root.after(0, lambda: self.set_loading(False))
                self.root.after(0, lambda: self._show_error_dialog("Launch Failed",
                    "Could not start Docker.\n\nPlease start Docker manually."))
                return

            # Poll until Docker is responsive (max 60s)
            docker_ready = False
            for _ in range(DOCKER_START_POLL_COUNT):
                if self.stop_event.is_set():
                    return
                is_running, _ = is_docker_running()
                if is_running:
                    docker_ready = True
                    break
                time.sleep(1)

            time.sleep(2)
            self.root.after(0, lambda: self.set_loading(False))

            if not docker_ready:
                self.root.after(0, lambda: self._show_error_dialog("Timeout",
                    "Docker did not start within 60 seconds.\n\nPlease start Docker manually and try again."))

            self.root.after(200, self.check_state)

        threading.Thread(target=_launch_thread).start()

    def check_update(self):
        """Manual update check - checks Docker Hub for updates and shows appropriate dialog."""
        self.lbl_update.configure(text="Checking...", text_color=NOVA_TEAL)
        self.set_loading(True, "Checking Docker Hub for updates...")
        threading.Thread(target=self._check_update_process, daemon=True).start()

    def _check_update_process(self):
        """Background thread to check for updates and show appropriate dialog."""
        try:
            # Check Docker Hub for updates
            update_available, remote_digest, error = check_dockerhub_version()

            if error:
                # Check failed - show error dialog
                self._append_log(f"[warn] Update check failed: {error}")
                self.root.after(0, lambda: self._show_info_dialog(
                    "Update Check Failed",
                    "Could not reach Docker Hub. Please check your internet connection."
                ))

            elif update_available and remote_digest:
                # Update available - show update dialog
                self._append_log(f"[info] Update available on Docker Hub")
                self.pending_update_digest = remote_digest
                # Use default argument to capture value, not reference
                self.root.after(0, lambda d=remote_digest: self._prompt_update_dialog(
                    d,
                    on_update_callback=self._perform_manual_update
                ))

            else:
                # No update available - show info dialog
                self._append_log("[info] Already on the latest version")
                local_digest = get_local_image_digest()
                # Use default argument to capture value
                self.root.after(0, lambda d=local_digest: self._show_info_dialog(
                    "No Update Available",
                    "Nova DSO Tracker is already on the latest version.",
                    digest=d
                ))

        except Exception as e:
            self._append_log(f"[error] Update check error: {e}")
            self.root.after(0, lambda: self._show_info_dialog(
                "Update Check Failed",
                f"An error occurred while checking for updates.\n\n{str(e)}"
            ))

        finally:
            # Reset UI state
            self.root.after(0, lambda: self.lbl_update.configure(text="↻ Check for Updates", text_color=NOVA_TEAL))
            self.root.after(0, lambda: self.set_loading(False))

    # --- Launcher Self-Update Check ---

    def _check_launcher_update(self):
        """Check GitHub releases for a newer launcher version."""
        try:
            req = urllib.request.Request(GITHUB_RELEASES_API, headers={"User-Agent": "NovaLauncher"})
            with urllib.request.urlopen(req, timeout=5, context=_SSL_CONTEXT) as response:
                data = json.loads(response.read().decode())
                latest_tag = data.get("tag_name", "").lstrip("v")
                html_url = data.get("html_url", "")

                if latest_tag and version_newer(latest_tag, APP_VERSION):
                    self.root.after(0, lambda: self._show_update_banner(latest_tag, html_url))
        except Exception:
            pass  # Silently fail - this is a nice-to-have

    def _show_update_banner(self, version, url):
        """Show a non-intrusive banner when a new launcher version is available."""
        self.lbl_update_banner.configure(
            text=f"Launcher v{version} available — click to download")
        self.lbl_update_banner.bind("<Button-1>", lambda e: webbrowser.open(url))
        self.update_banner.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))


if __name__ == "__main__":
    root = ctk.CTk()
    app = NovaManagerApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
