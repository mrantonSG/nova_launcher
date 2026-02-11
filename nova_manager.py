import shutil
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import time
import webbrowser
import urllib.request
import urllib.error
import socket
import os
import sys

# --- Configuration (centralized constants) ---
APP_NAME = "Nova DSO Tracker"
APP_VERSION = "1.2.0"
DOCKER_CONTAINER_NAME = "nova-tracker"
DOCKER_IMAGE = "mrantonsg/nova-dso-tracker"
DOCKER_TAG = "latest"
DOCKER_IMAGE_FULL = f"{DOCKER_IMAGE}:{DOCKER_TAG}"
PORT = 5001
DASHBOARD_URL = f"http://localhost:{PORT}"
DOCKER_DOWNLOAD_URL = "https://www.docker.com/products/docker-desktop"
GITHUB_REPO = "mrantonsg/nova-dso-tracker-launcher"
GITHUB_RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# FORCE INSTALL PATH to ~/nova (Universal & Safe)
INSTALL_PATH = os.path.join(os.path.expanduser("~"), "nova")
COMPOSE_FILE = os.path.join(INSTALL_PATH, "docker-compose.yml")

COMPOSE_TEMPLATE = f"""services:
  tracker:
    image: {DOCKER_IMAGE_FULL}
    container_name: {DOCKER_CONTAINER_NAME}
    ports:
      - "{PORT}:{PORT}"
    volumes:
      - ./instance:/app/instance
    restart: unless-stopped"""

# Command timeout (seconds)
DOCKER_CMD_TIMEOUT = 300

# --- Colors ---
BG_COLOR = "#FFFFFF"
NOVA_TEAL = "#6096BA"
NOVA_RED = "#D35454"
TEXT_COLOR = "#333333"
SUBTEXT_COLOR = "#666666"
SUCCESS_COLOR = "#4CD964"
WARNING_COLOR = "#FF9500"
GRAY_DOT = "#C7C7CC"
DANGER_COLOR = "#D35454"
LOG_BG = "#1E1E1E"
LOG_FG = "#D4D4D4"


class ModernButton(tk.Canvas):
    """Custom button for consistent macOS/Windows styling."""

    def __init__(self, parent, text, command, bg_color, width=140, height=38):
        super().__init__(parent, width=width, height=height, bg=BG_COLOR, highlightthickness=0)
        self.command = command
        self.bg_color = bg_color
        self.text = text
        self.is_disabled = False

        # Rounded Rect
        self.rect = self.create_rounded_rect(2, 2, width - 2, height - 2, 8, fill=bg_color, outline=bg_color)
        self.text_id = self.create_text(width / 2, height / 2, text=text, fill="white", font=("Helvetica", 13, "bold"))

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda e: self.config(cursor="hand2"))
        self.bind("<Leave>", lambda e: self.config(cursor=""))

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = (x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y1 + r, x2, y2 - r, x2,
                  y2 - r, x2, y2, x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y2 - r, x1,
                  y1 + r, x1, y1 + r, x1, y1)
        return self.create_polygon(points, **kwargs, smooth=True)

    def _on_click(self, event):
        if not self.is_disabled and self.command:
            self.command()

    def set_text(self, text):
        self.itemconfig(self.text_id, text=text)

    def set_color(self, color):
        self.bg_color = color
        self.itemconfig(self.rect, fill=color, outline=color)

    def set_state(self, state):
        self.is_disabled = (state == "disabled")
        color = "#AAAAAA" if self.is_disabled else self.bg_color
        self.itemconfig(self.rect, fill=color, outline=color)


class NovaManagerApp:
    def resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and for PyInstaller."""
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)

    def __init__(self, root):
        self.root = root

        # --- FIX ENV PATH ---
        if sys.platform == "darwin":
            os.environ["PATH"] += os.pathsep + "/usr/local/bin" + os.pathsep + "/opt/homebrew/bin"

        self.root.title("Nova DSO Tracker Launcher")
        self.root.geometry("500x580")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_COLOR)

        # Graceful shutdown handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if not os.path.exists(INSTALL_PATH):
            try:
                os.makedirs(INSTALL_PATH)
            except Exception as e:
                messagebox.showerror("Error", f"Cannot create install directory:\n{INSTALL_PATH}\n\n{e}")

        self.is_processing = False
        self.just_installed = False
        self.stop_event = threading.Event()
        self.log_lines = []

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
        header = tk.Frame(self.root, bg=BG_COLOR)
        header.pack(fill=tk.X, padx=30, pady=(30, 20))

        # Logo
        try:
            img_path = self.resource_path("nova_logo.png")
            self.logo_img = tk.PhotoImage(file=img_path)
            img_h = self.logo_img.height()
            if img_h > 70:
                factor = img_h // 70
                if factor > 1:
                    self.logo_img = self.logo_img.subsample(factor, factor)
            lbl_logo = tk.Label(header, image=self.logo_img, bg=BG_COLOR)
            lbl_logo.pack(side=tk.LEFT, padx=(0, 15))
        except Exception:
            lbl_logo = tk.Label(header, text="N", font=("Helvetica", 45, "bold"), fg=NOVA_TEAL, bg=BG_COLOR)
            lbl_logo.pack(side=tk.LEFT, padx=(0, 15))

        # Title Block
        title_frame = tk.Frame(header, bg=BG_COLOR)
        title_frame.pack(side=tk.LEFT, anchor="center")
        tk.Label(title_frame, text=APP_NAME, font=("Helvetica", 20, "bold"), bg=BG_COLOR, fg=TEXT_COLOR).pack(anchor="w")
        self.lbl_status_header = tk.Label(title_frame, text="Initializing...", font=("Helvetica", 13), bg=BG_COLOR,
                                          fg=SUBTEXT_COLOR)
        self.lbl_status_header.pack(anchor="w")

        # Status Dot
        self.dot_canvas = tk.Canvas(header, width=16, height=16, bg=BG_COLOR, highlightthickness=0)
        self.dot_id = self.dot_canvas.create_oval(2, 2, 14, 14, fill=GRAY_DOT, outline="")
        self.dot_canvas.pack(side=tk.RIGHT)

        # Divider
        tk.Frame(self.root, height=1, bg="#E5E5E5").pack(fill=tk.X, pady=(0, 10))

        # --- Content Area ---
        self.content_frame = tk.Frame(self.root, bg=BG_COLOR)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=20)

        # Center Status Text
        self.lbl_center_info = tk.Label(self.content_frame, text="Checking status...", font=("Helvetica", 12),
                                        bg=BG_COLOR, fg=SUBTEXT_COLOR, wraplength=400, justify="center")
        self.lbl_center_info.pack(pady=(20, 5))

        # Progress Bar
        self.progress = ttk.Progressbar(self.content_frame, mode='indeterminate', length=200)

        # Buttons Row
        self.btn_row = tk.Frame(self.content_frame, bg=BG_COLOR)
        self.btn_row.pack(pady=15)

        self.btn_main = ModernButton(self.btn_row, "Loading...", self.on_main_action, NOVA_TEAL)
        self.btn_main.pack(side=tk.LEFT, padx=10)

        self.btn_stop = ModernButton(self.btn_row, "Stop Tracker", self.stop_nova, NOVA_RED)

        # Version / image info label
        self.lbl_version = tk.Label(self.content_frame, text="", font=("Helvetica", 10), bg=BG_COLOR, fg=SUBTEXT_COLOR)
        self.lbl_version.pack(pady=(5, 0))

        # --- Log Viewer ---
        log_frame = tk.Frame(self.root, bg=BG_COLOR)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(5, 5))

        log_header = tk.Frame(log_frame, bg=BG_COLOR)
        log_header.pack(fill=tk.X)
        tk.Label(log_header, text="Logs", font=("Helvetica", 10, "bold"), bg=BG_COLOR, fg=SUBTEXT_COLOR).pack(
            side=tk.LEFT)

        self.log_toggle_var = tk.BooleanVar(value=False)
        self.log_toggle_btn = tk.Label(log_header, text="Show", font=("Helvetica", 10), bg=BG_COLOR,
                                        fg=NOVA_TEAL, cursor="hand2")
        self.log_toggle_btn.pack(side=tk.RIGHT)
        self.log_toggle_btn.bind("<Button-1>", lambda e: self._toggle_logs())

        self.log_text = tk.Text(log_frame, height=10, bg=LOG_BG, fg=LOG_FG, font=("Menlo", 10),
                                state="disabled", wrap="word", borderwidth=0, highlightthickness=0)
        # Start hidden
        self.log_text.pack_forget()

        # --- Footer ---
        footer = tk.Frame(self.root, bg=BG_COLOR)
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 15))

        # Update Link
        self.lbl_update = tk.Label(footer, text="\u27F3 Check for Updates", font=("Helvetica", 11), bg=BG_COLOR,
                                   fg=SUBTEXT_COLOR, cursor="hand2")
        self.lbl_update.pack(side=tk.BOTTOM, pady=(10, 0))
        self.lbl_update.bind("<Button-1>", lambda e: self.check_update())

        # Launcher version label
        self.lbl_launcher_ver = tk.Label(footer, text=f"Launcher v{APP_VERSION}", font=("Helvetica", 9),
                                          bg=BG_COLOR, fg="#AAAAAA")
        self.lbl_launcher_ver.pack(side=tk.BOTTOM)

        # Launcher update banner (hidden by default)
        self.update_banner = tk.Frame(footer, bg="#E8F5E9")
        self.lbl_update_banner = tk.Label(self.update_banner, text="", font=("Helvetica", 10),
                                           bg="#E8F5E9", fg="#2E7D32", cursor="hand2")
        self.lbl_update_banner.pack(padx=10, pady=5)

    def _toggle_logs(self):
        if self.log_toggle_var.get():
            self.log_text.pack_forget()
            self.log_toggle_btn.config(text="Show")
            self.log_toggle_var.set(False)
        else:
            self.log_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
            self.log_toggle_btn.config(text="Hide")
            self.log_toggle_var.set(True)

    def _append_log(self, text):
        """Thread-safe append to the log viewer."""
        def _update():
            self.log_text.config(state="normal")
            timestamp = time.strftime("%H:%M:%S")
            self.log_text.insert("end", f"[{timestamp}] {text}\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.root.after(0, _update)

    # --- UI Helpers ---

    def set_loading(self, is_loading, message="Processing..."):
        self.is_processing = is_loading
        if is_loading:
            self.lbl_center_info.config(text=message)
            self.progress.pack(after=self.lbl_center_info, pady=(10, 15))
            self.progress.start(10)
            self.btn_main.set_state("disabled")
            self.btn_stop.set_state("disabled")
            self.lbl_update.unbind("<Button-1>")
            self.lbl_update.config(fg="#AAAAAA", cursor="")
        else:
            self.progress.stop()
            self.progress.pack_forget()
            self.lbl_update.bind("<Button-1>", lambda e: self.check_update())
            self.lbl_update.config(fg=SUBTEXT_COLOR, cursor="hand2")
            self.lbl_center_info.config(text="")

    def run_command(self, command, timeout=DOCKER_CMD_TIMEOUT):
        """Run command inside ~/nova. Returns (stdout, stderr, returncode)."""
        self._append_log(f"$ {command}")
        try:
            result = subprocess.run(
                command, shell=True, cwd=INSTALL_PATH, env=os.environ,
                capture_output=True, text=True, timeout=timeout
            )
            if result.stdout.strip():
                self._append_log(result.stdout.strip())
            if result.stderr.strip():
                self._append_log(f"[stderr] {result.stderr.strip()}")
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except subprocess.TimeoutExpired:
            self._append_log(f"[timeout] Command timed out after {timeout}s")
            return "", f"Command timed out after {timeout}s", -1
        except Exception as e:
            self._append_log(f"[error] {e}")
            return "", str(e), -1

    def _run_command_compat(self, command, timeout=DOCKER_CMD_TIMEOUT):
        """Backward-compat wrapper that returns just stdout for simple checks."""
        stdout, _, _ = self.run_command(command, timeout=timeout)
        return stdout

    def check_port_available(self):
        """Check if the configured port is available before starting."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("127.0.0.1", PORT))
                if result == 0:
                    # Port is in use - check if it's our container
                    stdout = self._run_command_compat(
                        f'docker ps --filter "name={DOCKER_CONTAINER_NAME}" --format "{{{{.Status}}}}"',
                        timeout=10
                    )
                    if "Up" in stdout:
                        return True  # Our container is using it, that's fine
                    return False  # Something else is using the port
                return True  # Port is free
        except Exception:
            return True  # If check fails, proceed anyway

    def check_web_ready(self):
        """Check if the dashboard is responsive."""
        try:
            with urllib.request.urlopen(DASHBOARD_URL, timeout=2.0) as response:
                if response.getcode() != 200:
                    return False
                content = response.read()
                return len(content) > 500
        except Exception:
            return False

    def get_image_version(self):
        """Get the currently running image digest (short hash) for display."""
        try:
            stdout = self._run_command_compat(
                f'docker inspect --format="{{{{.Image}}}}" {DOCKER_CONTAINER_NAME}',
                timeout=10
            )
            if stdout and "sha256:" in stdout:
                return stdout.replace("sha256:", "")[:12]
            return ""
        except Exception:
            return ""

    def monitor_loop(self):
        while not self.stop_event.is_set():
            if not self.is_processing:
                self.check_state()
            time.sleep(3)

    def check_state(self):
        # 1. Docker installed?
        if shutil.which("docker") is None:
            self.update_ui("docker_missing")
            return

        # 2. Docker daemon running?
        stdout = self._run_command_compat("docker info", timeout=10)
        if "Server Version" not in stdout:
            self.update_ui("docker_stopped")
            return

        # 3. Nova installed?
        if not os.path.exists(COMPOSE_FILE):
            self.update_ui("not_installed")
            return

        # 4. Container running?
        status = self._run_command_compat(
            f'docker ps --filter "name={DOCKER_CONTAINER_NAME}" --format "{{{{.Status}}}}"',
            timeout=10
        )

        if "Up" in status:
            if self.check_web_ready():
                self.update_ui("running")
            else:
                self.update_ui("initializing")
        else:
            self.update_ui("stopped")

    def update_ui(self, state):
        self.root.after(0, lambda: self._apply_ui_state(state))

    def _apply_ui_state(self, state):
        if self.is_processing:
            return

        self.btn_main.set_state("normal")
        self.btn_stop.set_state("normal")

        if state == "docker_missing":
            self.set_status("Docker Missing", DANGER_COLOR,
                            "Docker Desktop is required to run Nova.\n\n"
                            "Click below to download it. Once installed,\n"
                            "open Docker Desktop and return here.")
            self.btn_main.set_text("Download Docker")
            self.btn_main.command = self.open_docker
            self.btn_main.set_color(NOVA_TEAL)
            self.btn_stop.pack_forget()
            self.lbl_version.config(text="")

        elif state == "docker_stopped":
            self.set_status("Docker Not Running", WARNING_COLOR, "Please open Docker Desktop to continue.")
            self.btn_main.set_text("Launch Docker")
            self.btn_main.command = self.launch_docker_app
            self.btn_main.set_color(NOVA_TEAL)
            self.btn_stop.pack_forget()
            self.lbl_version.config(text="")

        elif state == "not_installed":
            self.set_status("Not Installed", GRAY_DOT, f"Install location: {INSTALL_PATH}")
            self.btn_main.set_text("Install Nova")
            self.btn_main.command = self.install_nova
            self.btn_main.set_color(NOVA_TEAL)
            self.btn_stop.pack_forget()
            self.lbl_version.config(text="")

        elif state == "stopped":
            self.set_status("Service Stopped", WARNING_COLOR, "Service is stopped.")
            self.btn_main.set_text("Start Tracker")
            self.btn_main.command = self.start_nova
            self.btn_main.set_color(NOVA_TEAL)
            self.btn_stop.pack_forget()
            self._update_version_label()

        elif state == "initializing":
            if self.just_installed:
                msg = "First-time setup: Web UI may take ~2 mins to initialize.\nSubsequent runs will be real-time."
                self.set_status("Initializing...", WARNING_COLOR, msg)
            else:
                self.set_status("Initializing...", WARNING_COLOR, "Starting up... (this may take a minute)")
            self.btn_main.set_text("Open Dashboard")
            self.btn_main.command = self.open_dashboard
            self.btn_main.set_color(NOVA_TEAL)
            self.btn_stop.pack(side=tk.LEFT, padx=10)
            self._update_version_label()

        elif state == "running":
            self.just_installed = False
            self.set_status("Nova Tracker is Active", SUCCESS_COLOR, "")
            self.lbl_center_info.config(text="")
            self.btn_main.set_text("Open Dashboard")
            self.btn_main.command = self.open_dashboard
            self.btn_main.set_color(NOVA_TEAL)
            self.btn_stop.pack(side=tk.LEFT, padx=10)
            self._update_version_label()

    def _update_version_label(self):
        """Show the running image digest in the version label."""
        def _fetch():
            digest = self.get_image_version()
            if digest:
                self.root.after(0, lambda: self.lbl_version.config(
                    text=f"Image: {DOCKER_IMAGE}:{DOCKER_TAG}  \u2022  {digest}"))
            else:
                self.root.after(0, lambda: self.lbl_version.config(text=""))
        threading.Thread(target=_fetch, daemon=True).start()

    def set_status(self, header, dot, center):
        self.lbl_status_header.config(text=header)
        self.dot_canvas.itemconfig(self.dot_id, fill=dot)
        self.lbl_center_info.config(text=center)

    # --- Actions ---

    def on_main_action(self):
        pass

    def install_nova(self):
        self.just_installed = True
        self.set_loading(True, "Initializing installation...")

        try:
            os.makedirs(INSTALL_PATH, exist_ok=True)
        except Exception as e:
            self._append_log(f"[error] Cannot create directory {INSTALL_PATH}: {e}")
            messagebox.showerror("Installation Error",
                                 f"Cannot create install directory:\n{INSTALL_PATH}\n\n{e}")
            self.set_loading(False)
            return

        try:
            with open(COMPOSE_FILE, "w") as f:
                f.write(COMPOSE_TEMPLATE)
            self._append_log(f"Wrote docker-compose.yml to {COMPOSE_FILE}")
        except PermissionError:
            self._append_log(f"[error] Permission denied writing to {COMPOSE_FILE}")
            messagebox.showerror("Installation Error",
                                 f"Permission denied writing to:\n{COMPOSE_FILE}\n\n"
                                 "Please check directory permissions.")
            self.set_loading(False)
            return
        except OSError as e:
            self._append_log(f"[error] Failed to write docker-compose.yml: {e}")
            messagebox.showerror("Installation Error",
                                 f"Failed to write docker-compose.yml:\n{e}")
            self.set_loading(False)
            return

        threading.Thread(target=self._perform_install_sequence).start()

    def _perform_install_sequence(self):
        self.root.after(0, lambda: self.lbl_center_info.config(text="Downloading images... (this may take 2-3 mins)"))

        stdout, stderr, rc = self.run_command("docker compose pull")
        if rc != 0:
            self.root.after(0, lambda: messagebox.showerror("Pull Failed",
                                                             f"Failed to pull Docker image.\n\n{stderr}"))
            self.root.after(0, lambda: self.set_loading(False))
            return

        msg = "First-time setup: Web UI may take ~2 mins to initialize.\nSubsequent runs will be real-time."
        self.root.after(0, lambda: self.lbl_center_info.config(text=msg))

        self.run_command("docker compose up -d")

        # Poll until Container is officially "Up" (max 30s)
        for _ in range(30):
            status = self._run_command_compat(
                f'docker ps --filter "name={DOCKER_CONTAINER_NAME}" --format "{{{{.Status}}}}"',
                timeout=10
            )
            if "Up" in status:
                break
            time.sleep(1)

        self.root.after(0, lambda: self.set_loading(False))
        self.root.after(200, self.check_state)

    def start_nova(self):
        # Port conflict check
        if not self.check_port_available():
            messagebox.showwarning("Port Conflict",
                                   f"Port {PORT} is already in use by another application.\n\n"
                                   f"Please free port {PORT} and try again.")
            self._append_log(f"[warn] Port {PORT} is in use by another process")
            return
        self.set_loading(True, "Starting service...")
        threading.Thread(target=self._run_docker_op, args=("docker compose up -d",)).start()

    def stop_nova(self):
        self.set_loading(True, "Stopping service...")
        threading.Thread(target=self._run_docker_op, args=("docker compose stop",)).start()

    def _run_docker_op(self, cmd):
        stdout, stderr, rc = self.run_command(cmd)
        if rc != 0 and rc != -1:
            self._append_log(f"[warn] Command exited with code {rc}")
        time.sleep(2)
        self.root.after(0, lambda: self.set_loading(False))
        self.check_state()

    def open_dashboard(self):
        webbrowser.open(DASHBOARD_URL)

    def open_docker(self):
        webbrowser.open(DOCKER_DOWNLOAD_URL)

    def launch_docker_app(self):
        self.set_loading(True, "Launching Docker...")

        def _launch_thread():
            try:
                if sys.platform == "darwin":
                    subprocess.run(["open", "-a", "Docker"])
                elif sys.platform == "win32":
                    win_path = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"
                    if os.path.exists(win_path):
                        os.startfile(win_path)
                    else:
                        subprocess.run(["start", "docker"], shell=True)
                elif sys.platform == "linux":
                    subprocess.run(["systemctl", "start", "docker"])
            except Exception as e:
                self._append_log(f"[error] Docker launch failed: {e}")

            for _ in range(60):
                if self.stop_event.is_set():
                    return
                stdout = self._run_command_compat("docker info", timeout=10)
                if "Server Version" in stdout:
                    break
                time.sleep(1)

            time.sleep(2)
            self.root.after(0, lambda: self.set_loading(False))
            self.root.after(200, self.check_state)

        threading.Thread(target=_launch_thread).start()

    def check_update(self):
        self.lbl_update.config(text="Checking...", fg=NOVA_TEAL)
        self.set_loading(True, "Checking for updates...")
        threading.Thread(target=self._update_process).start()

    def _update_process(self):
        # 1. Pull the latest image
        stdout, stderr, rc = self.run_command(f"docker pull {DOCKER_IMAGE_FULL}")
        if rc != 0:
            self.root.after(0, lambda: messagebox.showerror("Update Failed",
                                                             f"Failed to pull the latest image.\n\n{stderr}"))
            self.root.after(0, lambda: self.set_loading(False))
            self.root.after(0, lambda: self.lbl_update.config(text="\u27F3 Check for Updates", fg=SUBTEXT_COLOR))
            return

        # 2. Stop current container
        self.run_command("docker compose stop")

        # 3. Force recreate
        self.run_command("docker compose up -d --force-recreate")

        # 4. Cleanup
        self.run_command("docker image prune -f")

        time.sleep(1)
        self.root.after(0, lambda: self.lbl_update.config(text="\u27F3 Update Applied", fg=SUCCESS_COLOR))

        self.root.after(0, lambda: self.set_loading(False))
        self.root.after(200, self.check_state)

        time.sleep(3)
        self.root.after(0, lambda: self.lbl_update.config(text="\u27F3 Check for Updates", fg=SUBTEXT_COLOR))

    # --- Launcher Self-Update Check ---

    def _check_launcher_update(self):
        """Check GitHub releases for a newer launcher version."""
        try:
            req = urllib.request.Request(GITHUB_RELEASES_API, headers={"User-Agent": "NovaLauncher"})
            with urllib.request.urlopen(req, timeout=5) as response:
                import json
                data = json.loads(response.read().decode())
                latest_tag = data.get("tag_name", "").lstrip("v")
                html_url = data.get("html_url", "")

                if latest_tag and self._version_newer(latest_tag, APP_VERSION):
                    self.root.after(0, lambda: self._show_update_banner(latest_tag, html_url))
        except Exception:
            pass  # Silently fail - this is a nice-to-have

    @staticmethod
    def _version_newer(remote, local):
        """Compare semver strings. Returns True if remote > local."""
        try:
            r = tuple(int(x) for x in remote.split("."))
            l = tuple(int(x) for x in local.split("."))
            return r > l
        except Exception:
            return False

    def _show_update_banner(self, version, url):
        """Show a non-intrusive banner when a new launcher version is available."""
        self.lbl_update_banner.config(
            text=f"Launcher v{version} available \u2014 click to download")
        self.lbl_update_banner.bind("<Button-1>", lambda e: webbrowser.open(url))
        self.update_banner.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))


if __name__ == "__main__":
    root = tk.Tk()
    app = NovaManagerApp(root)
    root.mainloop()
