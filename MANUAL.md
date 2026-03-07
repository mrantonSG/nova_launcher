# Nova DSO Tracker Launcher - User Manual

**Version 1.2.5-beta.1**

---

## Table of Contents

1. [Introduction](#introduction)
2. [System Requirements](#system-requirements)
3. [Installation](#installation)
   - [macOS](#macos-installation)
   - [Windows](#windows-installation)
   - [Linux](#linux-installation)
4. [Getting Started](#getting-started)
5. [Application Interface](#application-interface)
6. [Functionality Guide](#functionality-guide)
   - [Docker Status](#docker-status)
   - [Installation](#installation)
   - [Service Management](#service-management)
   - [Web Dashboard](#web-dashboard)
   - [Updates](#updates)
   - [Log Viewer](#log-viewer)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Usage](#advanced-usage)
9. [Uninstallation](#uninstallation)

---

## Introduction

Nova DSO Tracker Launcher is a cross-platform GUI application that simplifies the installation, configuration, and management of the Nova DSO Tracker (Deep Space Object tracking system). The launcher provides a user-friendly interface to manage the underlying Docker containerized application without requiring command-line knowledge.

**Key Features:**
- One-click Docker-based installation
- Real-time service status monitoring
- Automatic update checking for both the tracker image and launcher itself
- Built-in log viewer for troubleshooting
- Cross-platform support (macOS, Windows, Linux)
- Graceful Docker daemon management

---

## System Requirements

### Common Requirements (All Platforms)

| Requirement | Minimum | Recommended |
|-------------|----------|-------------|
| **RAM** | 4 GB | 8 GB or more |
| **Disk Space** | 2 GB free | 5 GB or more |
| **Internet** | Broadband connection for initial download and updates | Stable connection |
| **Docker** | Docker Desktop installed and running | Latest version of Docker Desktop |

### Platform-Specific Requirements

**macOS**
- macOS 10.15 (Catalina) or later
- Intel or Apple Silicon (M1/M2/M3) processor

**Windows**
- Windows 10 (version 1903) or Windows 11
- 64-bit operating system

**Linux**
- Any modern distribution (Ubuntu 20.04+, Debian 10+, Fedora 34+, Arch Linux, etc.)
- systemd support for Docker service management

---

## Installation

### macOS Installation

1. **Install Docker Desktop**
   - Download Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop)
   - Install the package and launch Docker Desktop
   - Wait for the Docker whale icon in the menu bar to stop animating (indicating it's ready)

2. **Download Nova Launcher**
   - Download `Nova DSO Tracker.zip` from the [Releases page](https://github.com/mrantonsg/nova-dso-tracker-launcher/releases)
   - Unzip the downloaded file
   - You will see `Nova DSO Tracker.app`

3. **Install the Application**
   - Drag `Nova DSO Tracker.app` to your **Applications** folder
   - Alternatively, keep it on your Desktop or any preferred location

4. **First Launch**
   - Double-click `Nova DSO Tracker.app` to launch
   - **Important:** On first launch of an unsigned app, macOS will block it:
     - Open **System Settings** → **Privacy & Security**
     - Scroll down to the security message about "Nova DSO Tracker"
     - Click **"Open Anyway"** to allow the app
     - You may be prompted to enter your password
   - This only needs to be done once

**Note:** The right-click → "Open" method no longer works on recent macOS versions. You must use the Privacy & Security settings.

### Windows Installation

1. **Install Docker Desktop**
   - Download Docker Desktop for Windows from [docker.com](https://www.docker.com/products/docker-desktop)
   - Run the installer and follow the prompts
   - Ensure WSL 2 (Windows Subsystem for Linux) is installed when prompted
   - Reboot your computer if required
   - Launch Docker Desktop and wait for it to be ready

2. **Download Nova Launcher**
   - Download `Nova DSO Tracker.exe` from the [Releases page](https://github.com/mrantonsg/nova-dso-tracker-launcher/releases)
   - (If only a .zip is available, unzip it to locate the .exe file)

3. **Install/Run the Application**
   - Place `Nova DSO Tracker.exe` in a convenient location (e.g., `C:\Program Files\Nova Launcher`)
   - Right-click and select "Run as administrator" for the first run (recommended)
   - You may create a desktop shortcut for easier access:
     - Right-click the `.exe` file
     - Select "Send to" → "Desktop (create shortcut)"

4. **Windows Defender/Security**
   - If Windows SmartScreen blocks the app:
     - Click "More info"
     - Select "Run anyway"

### Linux Installation

1. **Install Docker**
   - The installation method varies by distribution. Choose your distro:

   **Ubuntu/Debian:**
   ```bash
   sudo apt-get update
   sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin
   sudo usermod -aG docker $USER
   ```
   Log out and back in for group changes to take effect.

   **Fedora:**
   ```bash
   sudo dnf install docker-ce docker-ce-cli containerd.io docker-compose-plugin
   sudo systemctl enable --now docker
   sudo usermod -aG docker $USER
   ```

   **Arch Linux:**
   ```bash
   sudo pacman -S docker docker-compose
   sudo systemctl enable --now docker
   sudo usermod -aG docker $USER
   ```

2. **Verify Docker Installation**
   ```bash
   docker --version
   docker info  # Should return server information
   ```

3. **Download Nova Launcher**
   - Download the Linux package from the [Releases page](https://github.com/mrantonsg/nova-dso-tracker-launcher/releases)
   - Typically provided as `Nova DSO Tracker` (executable with no extension) or `.AppImage`

4. **Run the Application**
   ```bash
   chmod +x "Nova DSO Tracker"
   ./Nova\ DSO\ Tracker
   ```

5. **Create Desktop Entry (Optional)**
   Create a `.desktop` file at `~/.local/share/applications/nova-launcher.desktop`:
   ```ini
   [Desktop Entry]
   Name=Nova DSO Tracker Launcher
   Comment=Launcher for Nova DSO Tracker
   Exec=/path/to/Nova DSO Tracker
   Icon=nova-launcher
   Terminal=false
   Type=Application
   Categories=Science;Astronomy;
   ```

---

## Getting Started

After installing and launching the Nova DSO Tracker Launcher:

1. **Initial Status Check**
   - The launcher automatically checks:
     - If Docker is installed
     - If Docker daemon is running
     - If Nova DSO Tracker is installed

2. **Installation (First Time)**
   - If not installed, you'll see "Not Installed" status
   - Click "Install Nova" to begin the automatic installation
   - The process will:
     - Create necessary configuration files in `~/nova/` directory
     - Download the Docker image (may take 2-5 minutes depending on internet speed)
     - Start the container
   - First-time web UI initialization may take ~2 minutes

3. **Accessing the Dashboard**
   - Once the status shows "Nova Tracker is Active"
   - Click "Open Dashboard" to launch the web interface in your default browser
   - The dashboard will be available at `http://localhost:5001`

---

## Application Interface

### Main Window

The Nova Launcher window contains the following sections:

```
┌─────────────────────────────────────────────────────────┐
│  Nova DSO Tracker                      ● Running    │  ← Header with status
├─────────────────────────────────────────────────────────┤
│                                                      │
│              [Status Information]                       │  ← Center info
│                                                      │
│           [Primary Button]   [Stop Tracker]            │  ← Action buttons
│                                                      │
│  Image: mrantonsg/nova-dso-tracker:latest • abc123   │  ← Version info
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│  Logs                                    [Show]     │  ← Log viewer
│                                                      │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│                   Launcher v1.2.5                   │  ← Footer
│             ↻ Check for Updates                     │
└─────────────────────────────────────────────────────────┘
```

### Status Indicators

| Status Dot Color | Meaning |
|-----------------|---------|
| Teal ● | Nova Tracker is active and running |
| Gray ● | Service stopped or not installed |
| Orange ● | Initializing, Docker not running, or warning state |
| Red ● | Error condition |

### Button Types

| Button Style | Purpose |
|--------------|---------|
| Teal (Primary) | Main action button (Install, Start, Open Dashboard) |
| White/Gray (Ghost) | Secondary actions (Skip, etc.) |
| Red/White (Danger) | Destructive actions (Stop Tracker) |

---

## Functionality Guide

### Docker Status

The launcher continuously monitors Docker status in the background:

**Docker Missing**
- Docker Desktop is not installed
- Click "Download Docker" to visit the Docker download page
- Install Docker Desktop and return to the launcher

**Docker Not Running**
- Docker Desktop is installed but not running
- Click "Launch Docker" to automatically start it
- The launcher will wait up to 60 seconds for Docker to become ready

**Docker Running**
- Docker daemon is operational
- Launcher proceeds to check Nova installation status

### Installation

The installation process handles everything automatically:

1. **Directory Creation**
   - Creates `~/nova/` directory in your home folder
   - Contains docker-compose.yml and configuration files
   - Instance data is stored in `~/nova/instance/`

2. **Docker Compose File**
   - Automatically generates `docker-compose.yml` with proper configuration
   - Maps port 5001 from host to container
   - Sets up persistent volume for data storage
   - Configures automatic restart policy

3. **Image Download**
   - Pulls the latest image from Docker Hub: `mrantonsg/nova-dso-tracker:latest`
   - Shows progress in the log viewer
   - May take 2-5 minutes depending on internet speed

4. **Container Launch**
   - Automatically starts the container after download
   - Polls for up to 30 seconds for the container to reach "Up" state

### Service Management

**Start Tracker**
- Starts the Nova DSO Tracker container
- Performs a port conflict check before starting
- Polls for container readiness
- Shows "Initializing..." status until web UI is ready

**Stop Tracker**
- Gracefully stops the running container
- Maintains all persistent data
- Can be restarted at any time

**Restart**
- Not a direct button, but can be achieved by:
  1. Click "Stop Tracker"
  2. Wait for stop to complete
  3. Click "Start Tracker"

**Service Lifecycle**
- Container is configured with `restart: unless-stopped` policy
- Automatically restarts after system reboot
- Survives Docker Desktop restarts

### Web Dashboard

**Opening the Dashboard**
- Click "Open Dashboard" button when the status is "Nova Tracker is Active"
- Opens `http://localhost:5001` in your default web browser
- Dashboard may take up to 2 minutes to initialize on first run
- Subsequent runs load in real-time

**Platform-Specific Browser Behavior**
- **macOS**: Uses the `open` command, respecting your default browser setting
- **Linux**: Opens via webbrowser and attempts to bring to front with wmctrl (if available)
- **Windows**: Opens via webbrowser and uses PowerShell to bring the window to foreground

**Direct Access**
- You can also access the dashboard directly by typing `http://localhost:5001` in any browser
- The dashboard is accessible from other devices on your local network using your computer's IP address

### Updates

**Automatic Image Updates**
- The launcher checks Docker Hub for updates once per session
- Compares local image digest with remote registry
- Prompts you when a new version is available

**Update Dialog Options:**
- **Update Now**: Downloads the latest image, recreates the container, and auto-starts
- **Skip**: Dismisses the notification for this session only
- **Skip Version**: Marks this version as skipped and won't notify again for this specific update

**Manual Update Check**
- Click "↻ Check for Updates" at any time
- Checks for Docker Hub updates
- Shows appropriate dialog:
  - Update available: Shows update dialog
  - Up to date: Shows confirmation with current image digest
  - Error: Shows failure reason (network issues, Docker Hub unavailable, etc.)

**Launcher Self-Updates**
- Checks GitHub Releases API for newer launcher versions
- Shows a non-intrusive green banner at the bottom if an update is available
- Click the banner to download the new version from GitHub releases
- Does not auto-install launcher updates (manual installation required)

**Update Process Details**
- When updating, the launcher:
  1. Pulls the latest Docker image
  2. Stops the running container
  3. Recreates the container with the new image
  4. Prunes old, unused images to save disk space
  5. Auto-starts the container (unless it was a manual check)

### Log Viewer

**Viewing Logs**
- Click "Show" next to the Logs header to expand the log viewer
- Each log entry includes a timestamp in `[HH:MM:SS]` format
- Shows Docker commands executed and their output

**Log Features**
- Automatically limits display to last 500 lines to prevent memory issues
- Automatically scrolls to show new entries
- Can be hidden by clicking "Hide"

**Log Content**
- Docker pull/download progress
- Container start/stop operations
- Error messages and warnings
- Information about version checks and updates

---

## Troubleshooting

### Docker Issues

**Docker Not Detected**
- Verify Docker Desktop is installed
- Check that Docker Desktop is running (menu bar icon on macOS, system tray on Windows)
- Try running `docker info` in terminal/command prompt
- Restart Docker Desktop if needed

**Docker Start Timeout**
- If launcher shows "Timeout" when launching Docker:
  - Start Docker Desktop manually
  - Wait for it to be fully ready (whale icon stops animating)
  - Click "Refresh" or restart the launcher

**Docker Permission Denied (Linux)**
- Ensure your user is in the docker group:
  ```bash
  groups | grep docker
  ```
- If not in group:
  ```bash
  sudo usermod -aG docker $USER
  ```
- Log out and log back in

### Installation Issues

**Download Fails**
- Check your internet connection
- Verify Docker Hub is accessible (visit hub.docker.com)
- Try again after a few minutes (Docker Hub may be rate-limiting)
- Check available disk space (at least 2 GB free)

**Port Already in Use**
- Error: "Port 5001 is already in use"
- Check if another application is using port 5001
- Stop the conflicting application
- Or check if Nova container is already running in another session

**Permission Denied Creating Directory**
- Ensure you have write permissions to `~/nova/`
- On Linux/macOS, check directory ownership: `ls -la ~/nova`
- On Windows, try running as administrator

### Container Issues

**Container Won't Start**
- Check the log viewer for error messages
- Verify docker-compose.yml exists and is valid
- Try manually from terminal:
  ```bash
  cd ~/nova
  docker compose up -d
  ```
- Check Docker disk space: `docker system df`

**Container Stopping Unexpectedly**
- Check Docker Desktop logs for crash information
- Verify system has sufficient RAM (minimum 4 GB)
- Check if container is being killed by OOM (Out Of Memory) killer

**Dashboard Not Accessible**
- Ensure container status shows "Nova Tracker is Active"
- Try accessing `http://localhost:5001` directly in browser
- Check firewall settings - port 5001 must be open for localhost
- Wait up to 2 minutes after first start (initialization takes time)

### Update Issues

**Update Check Fails**
- Verify internet connection
- Check if Docker Hub is accessible
- Docker Hub API may be temporarily unavailable
- Try again later

**Update Download Stalls**
- Large images may take time to download
- Check network speed
- Pause and resume may not work for Docker pulls
- If stuck for >10 minutes, cancel and try again

**Update Not Applied**
- After updating, verify container is running:
  ```bash
  docker ps
  ```
- Manually restart if needed:
  ```bash
  cd ~/nova
  docker compose restart
  ```

### Platform-Specific Issues

**macOS Gatekeeper Blocking**
- Go to **System Settings** → **Privacy & Security**
- Find the security message about the blocked app
- Click **"Open Anyway"** to allow it
- Enter your password if prompted

**Windows SmartScreen**
- Click "More info" then "Run anyway"
- Or disable SmartScreen (not recommended)

**Linux Wayland Issues**
- Some window managers may have issues
- Try with X11 backend if available
- Check terminal for error messages

---

## Advanced Usage

### Manual Docker Commands

For advanced users, you can manage Nova manually using Docker CLI:

**Start Container:**
```bash
cd ~/nova
docker compose up -d
```

**Stop Container:**
```bash
cd ~/nova
docker compose stop
```

**View Logs:**
```bash
cd ~/nova
docker compose logs -f
```

**Rebuild Container:**
```bash
cd ~/nova
docker compose up -d --force-recreate
```

**Access Container Shell:**
```bash
docker exec -it nova-tracker /bin/bash
```

### Configuration File

**Location:** `~/nova/docker-compose.yml`

**Contents:**
```yaml
services:
  tracker:
    image: mrantonsg/nova-dso-tracker:latest
    container_name: nova-tracker
    ports:
      - "5001:5001"
    volumes:
      - ./instance:/app/instance
    restart: unless-stopped
```

**Customization Options:**
- Change the port by modifying `ports:` section (e.g., `"8080:5001"`)
- Add environment variables with an `environment:` section
- Add additional volumes if needed

### Data Persistence

All Nova data is stored in:
- **Location:** `~/nova/instance/`
- **Preserved:** Across container restarts and updates
- **Backup:** Copy this directory to backup your data

### Preferences File

**Location:** `~/nova/.launcher_prefs.json`

**Contents:**
```json
{
  "skipped_digest": "sha256:abc123..."
}
```

- Stores which version you've chosen to skip
- Can be deleted to reset skip preferences
- Do not manually edit unless necessary

### Debug Mode

For troubleshooting, you can run the launcher from source with debug output:

```bash
# Clone repository
git clone https://github.com/mrantonsg/nova-dso-tracker-launcher.git
cd nova-dso-tracker-launcher

# Install dependencies
pip install -r requirements.txt

# Run with debug output
python3 nova_manager.py
```

Terminal output will show additional diagnostic information.

---

## Uninstallation

### macOS

1. **Stop and Remove Container**
   ```bash
   cd ~/nova
   docker compose down
   ```

2. **Remove Docker Image (Optional)**
   ```bash
   docker rmi mrantonsg/nova-dso-tracker:latest
   ```

3. **Remove Application**
   - Drag `Nova DSO Tracker.app` from Applications to Trash
   - Empty Trash

4. **Remove Data Directory (Optional)**
   - This will delete all your Nova data
   - Remove the `~/nova` directory:
   ```bash
   rm -rf ~/nova
   ```

### Windows

1. **Stop and Remove Container**
   ```powershell
   cd %USERPROFILE%\nova
   docker compose down
   ```

2. **Remove Docker Image (Optional)**
   ```powershell
   docker rmi mrantonsg/nova-dso-tracker:latest
   ```

3. **Uninstall Application**
   - Delete `Nova DSO Tracker.exe`
   - Remove any desktop shortcuts

4. **Remove Data Directory (Optional)**
   - Delete `%USERPROFILE%\nova` folder
   - This will delete all your Nova data

### Linux

1. **Stop and Remove Container**
   ```bash
   cd ~/nova
   docker compose down
   ```

2. **Remove Docker Image (Optional)**
   ```bash
   docker rmi mrantonsg/nova-dso-tracker:latest
   ```

3. **Uninstall Application**
   ```bash
   rm "Nova DSO Tracker"
   ```
   - Or remove the desktop entry:
   ```bash
   rm ~/.local/share/applications/nova-launcher.desktop
   ```

4. **Remove Data Directory (Optional)**
   ```bash
   rm -rf ~/nova
   ```

---

## Support

**Project Links:**
- **Main Project:** [Nova DSO Tracker](https://github.com/mrantonsg/nova-dso-tracker)
- **Docker Image:** [mrantonsg/nova-dso-tracker](https://hub.docker.com/r/mrantonsg/nova-dso-tracker)
- **Launcher Project:** [nova-dso-tracker-launcher](https://github.com/mrantonsg/nova-dso-tracker-launcher)
- **Website:** [https://nova-tracker.com](https://nova-tracker.com)

**Reporting Issues:**
- Report bugs on the GitHub Issues page
- Include:
  - Operating system and version
  - Launcher version (shown in footer)
  - Error messages from log viewer
  - Steps to reproduce

---

## License

Copyright © 2026 mrantonsg

All rights reserved. For license information, see the project repository.

---

*Document Version: 1.0*
*Last Updated: March 2026*
