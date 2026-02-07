# Nova DSO Tracker Launcher

<img src="nova_logo.png" alt="Nova DSO Tracker Logo" width="120">

A cross-platform GUI launcher for **Nova DSO Tracker**. This tool simplifies the installation and management of the Docker-based Nova tracker, providing a one-click experience for macOS, Windows, and Linux users.

---

##  Key Features

* **One-Click Setup:** Automatically checks for Docker, pulls the latest image, and installs the container.
* **Service Management:** Start, stop, and restart the tracking service with a single button.
* **Smart Monitoring:** Real-time status indicators for the Docker container and web dashboard availability.
* **Auto-Updates:** Built-in check to pull the latest version of the `nova-dso-tracker` image.
* **Cross-Platform:** Native executables for macOS (`.app`), Windows (`.exe`), and Linux.

##  Prerequisites

* **Docker Desktop** must be installed and running.
    * [Download Docker Desktop](https://www.docker.com/products/docker-desktop)

##  Installation

### macOS
1.  Download `Nova DSO Tracker.zip` from the **Releases** page.
2.  Unzip the file to get `Nova DSO Tracker.app`.
3.  Drag the app to your **Applications** folder (or Desktop).
4.  Double-click to launch.
    * *Note: On first launch, you may need to right-click > Open if the app is unsigned.*

### Windows, Linux
under development

##  Development

If you want to run the launcher from source or build it yourself:

### 1. Environment Setup
```bash
# Clone the repo
git clone [https://github.com/mrantonsg/nova-dso-tracker-launcher.git](https://github.com/mrantonsg/nova-dso-tracker-launcher.git)
cd nova-dso-tracker-launcher

# Create virtual environment (Recommended)
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt  # (Create this file with: tkinter is usually built-in, but pip install pyinstaller is needed)
pip install pyinstaller
```

### 2. Run from Source
```bash
python3 nova_manager.py
```

### 3. Build Executables

**macOS Build:**
```bash
# Ensure nova_logo.icns exists
python3 -m PyInstaller --noconfirm "Nova DSO Tracker.spec"
```

**Windows Build:**
*Note: Requires `nova_logo.ico` instead of `.icns`*
```powershell
pyinstaller --noconfirm --onefile --windowed --name "Nova DSO Tracker" --add-data "nova_logo.png;." --icon "nova_logo.ico" nova_manager.py
```

##  Links

* **Main Project:** [Nova DSO Tracker](https://github.com/mrantonsg/nova-dso-tracker)
* **Docker Image:** [mrantonsg/nova-dso-tracker](https://hub.docker.com/r/mrantonsg/nova-dso-tracker)

---
Copyright © 2026 mrantonsg