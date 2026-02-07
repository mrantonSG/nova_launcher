import tkinter as tk
from tkinter import ttk, filedialog
import subprocess
import threading
import time
import webbrowser
import urllib.request
import urllib.error
import json
import os
import sys

# --- Configuration ---
APP_NAME = "Nova DSO Tracker"
DOCKER_CONTAINER_NAME = "nova-tracker"
DOCKER_IMAGE = "mrantonsg/nova-dso-tracker:latest"
PORT = 5001

# FORCE INSTALL PATH to ~/nova (Universal & Safe)
INSTALL_PATH = os.path.join(os.path.expanduser("~"), "nova")

# --- Colors ---
BG_COLOR = "#FFFFFF"
NOVA_TEAL = "#6096BA"
NOVA_RED = "#D35454"
TEXT_COLOR = "#333333"
SUBTEXT_COLOR = "#666666"
SUCCESS_COLOR = "#4CD964"
WARNING_COLOR = "#FF9500"
GRAY_DOT = "#C7C7CC"


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
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)

    def __init__(self, root):
        self.root = root
        self.root.title("Nova DSO Tracker Launcher")
        self.root.geometry("500x450")  # Slightly shorter now that logs are gone
        self.root.resizable(False, False)
        self.root.configure(bg=BG_COLOR)

        if not os.path.exists(INSTALL_PATH):
            try:
                os.makedirs(INSTALL_PATH)
            except Exception as e:
                print(f"Error creating install dir: {e}")

        self.is_processing = False
        self.stop_event = threading.Event()

        self.setup_ui()

        # Start Background Monitor
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

    def setup_ui(self):
        # --- Header ---
        header = tk.Frame(self.root, bg=BG_COLOR)
        header.pack(fill=tk.X, padx=30, pady=30)

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
        # anchor="center" vertically aligns the text block relative to the logo
        title_frame.pack(side=tk.LEFT, anchor="center")
        tk.Label(title_frame, text=APP_NAME, font=("Helvetica", 20, "bold"), bg=BG_COLOR, fg=TEXT_COLOR).pack(
            anchor="w")
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
                                        bg=BG_COLOR, fg=SUBTEXT_COLOR)
        self.lbl_center_info.pack(pady=(30, 5))

        # Progress Bar
        self.progress = ttk.Progressbar(self.content_frame, mode='indeterminate', length=200)

        # Buttons Row
        self.btn_row = tk.Frame(self.content_frame, bg=BG_COLOR)
        self.btn_row.pack(pady=25)

        self.btn_main = ModernButton(self.btn_row, "Loading...", self.on_main_action, NOVA_TEAL)
        self.btn_main.pack(side=tk.LEFT, padx=10)

        self.btn_stop = ModernButton(self.btn_row, "Stop Tracker", self.stop_nova, NOVA_RED)

        # Update Link
        self.lbl_update = tk.Label(self.root, text="⟳ Check for Updates", font=("Helvetica", 11), bg=BG_COLOR,
                                   fg=SUBTEXT_COLOR, cursor="hand2")
        self.lbl_update.pack(side=tk.BOTTOM, pady=30)
        self.lbl_update.bind("<Button-1>", lambda e: self.check_update())

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
            self.btn_main.set_state("normal")
            self.btn_stop.set_state("normal")
            self.lbl_update.bind("<Button-1>", lambda e: self.check_update())
            self.lbl_update.config(fg=SUBTEXT_COLOR, cursor="hand2")
            self.lbl_center_info.config(text="")

    def run_command(self, command):
        """Run command inside ~/nova with fixed environment."""
        env = os.environ.copy()
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + env.get("PATH", "")
        try:
            result = subprocess.run(
                command, shell=True, cwd=INSTALL_PATH, env=env,
                capture_output=True, text=True
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def check_web_ready(self):
        """
        Checks if the dashboard is responsive.
        Retries briefly to avoid flickers during startup.
        """
        try:
            url = f"http://localhost:{PORT}"
            # Slightly longer timeout to allow the server to handle the request if it's busy
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if response.getcode() != 200:
                    return False

                # We expect significant content (>500 bytes) to confirm it's not a blank page
                content = response.read()
                return len(content) > 500
        except:
            return False

    def monitor_loop(self):
        while not self.stop_event.is_set():
            if not self.is_processing:
                self.check_state()
            time.sleep(3)  # Polling interval

    def check_state(self):
        # 1. Check Docker
        if "Docker version" not in self.run_command("docker --version"):
            self.update_ui("docker_missing")
            return

        # 2. Check File
        if not os.path.exists(os.path.join(INSTALL_PATH, "docker-compose.yml")):
            self.update_ui("not_installed")
            return

        # 3. Check Container
        status = self.run_command(f'docker ps --filter "name={DOCKER_CONTAINER_NAME}" --format "{{{{.Status}}}}"')

        if "Up" in status:
            # 4. Web Check
            if self.check_web_ready():
                self.update_ui("running")
            else:
                self.update_ui("initializing")
        else:
            self.update_ui("stopped")

    def update_ui(self, state):
        self.root.after(0, lambda: self._apply_ui_state(state))

    def _apply_ui_state(self, state):
        if self.is_processing: return

        if state == "docker_missing":
            self.set_status("Docker Missing", DANGER_COLOR, "Docker Desktop is required.")
            self.btn_main.set_text("Download Docker")
            self.btn_main.command = self.open_docker
            self.btn_stop.pack_forget()

        elif state == "not_installed":
            self.set_status("Not Installed", GRAY_DOT, f"Install location: {INSTALL_PATH}")
            self.btn_main.set_text("Install Nova")
            self.btn_main.command = self.install_nova
            self.btn_main.set_color(NOVA_TEAL)
            self.btn_stop.pack_forget()

        elif state == "stopped":
            self.set_status("Service Stopped", WARNING_COLOR, "Service is stopped.")
            self.btn_main.set_text("Start Tracker")
            self.btn_main.command = self.start_nova
            self.btn_main.set_color(NOVA_TEAL)
            self.btn_stop.pack_forget()

        elif state == "initializing":
            self.set_status("Initializing...", WARNING_COLOR, "Starting up... (this may take a minute)")
            self.btn_main.set_text("Open Dashboard")
            self.btn_main.command = self.open_dashboard
            self.btn_main.set_color(NOVA_TEAL)
            # Show Stop Button so user can abort if stuck
            self.btn_stop.pack(side=tk.LEFT, padx=10)

        elif state == "running":
            self.set_status("Nova Tracker is Active", SUCCESS_COLOR, "")
            self.lbl_center_info.config(text="")
            self.btn_main.set_text("Open Dashboard")
            self.btn_main.command = self.open_dashboard
            self.btn_main.set_color(NOVA_TEAL)
            self.btn_stop.pack(side=tk.LEFT, padx=10)

    def set_status(self, header, dot, center):
        self.lbl_status_header.config(text=header)
        self.dot_canvas.itemconfig(self.dot_id, fill=dot)
        self.lbl_center_info.config(text=center)

    # --- Actions ---

    def on_main_action(self):
        pass

    def install_nova(self):
        self.set_loading(True, "Initializing installation...")
        content = f"""
services:
  tracker:
    image: {DOCKER_IMAGE}
    container_name: {DOCKER_CONTAINER_NAME}
    ports:
      - "{PORT}:{PORT}"
    volumes:
      - ./instance:/app/instance
    restart: unless-stopped
"""
        try:
            with open(os.path.join(INSTALL_PATH, "docker-compose.yml"), "w") as f:
                f.write(content.strip())
            threading.Thread(target=self._perform_install_sequence).start()
        except Exception as e:
            print(f"Install Error: {e}")
            self.set_loading(False)

    def _perform_install_sequence(self):
        self.root.after(0, lambda: self.lbl_center_info.config(text="Downloading images... (this may take 2-3 mins)"))
        self.root.update_idletasks()
        self.run_command("docker compose pull")

        # First-time specific message
        msg = "First-time setup: Web UI may take ~2 mins to initialize.\nSubsequent runs will be real-time."
        self.root.after(0, lambda: self.lbl_center_info.config(text=msg))
        self.root.update_idletasks()
        self.run_command("docker compose up -d")

        time.sleep(3)
        self.root.after(0, lambda: self.set_loading(False))
        self.check_state()

    def start_nova(self):
        self.set_loading(True, "Starting service...")
        threading.Thread(target=self._run_docker_op, args=("docker compose up -d",)).start()

    def stop_nova(self):
        self.set_loading(True, "Stopping service...")
        threading.Thread(target=self._run_docker_op, args=("docker compose stop",)).start()

    def _run_docker_op(self, cmd):
        self.run_command(cmd)
        time.sleep(2)
        self.root.after(0, lambda: self.set_loading(False))
        self.check_state()

    def open_dashboard(self):
        webbrowser.open(f"http://localhost:{PORT}")

    def open_docker(self):
        webbrowser.open("https://www.docker.com/products/docker-desktop")

    def check_update(self):
        self.lbl_update.config(text="Checking...", fg=NOVA_TEAL)
        self.set_loading(True, "Checking for updates...")
        threading.Thread(target=self._update_process).start()

    def _update_process(self):
        self.run_command("docker compose pull")
        time.sleep(1)
        self.root.after(0, lambda: self.lbl_update.config(text="⟳ Update Check Complete", fg=SUCCESS_COLOR))
        self.root.after(0, lambda: self.set_loading(False))
        time.sleep(3)
        self.root.after(0, lambda: self.lbl_update.config(text="⟳ Check for Updates", fg=SUBTEXT_COLOR))


if __name__ == "__main__":
    root = tk.Tk()
    app = NovaManagerApp(root)
    root.mainloop()