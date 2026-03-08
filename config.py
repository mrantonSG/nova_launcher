# -*- coding: utf-8 -*-
"""
Configuration constants for Nova DSO Tracker Launcher.

All paths, timeouts, Docker settings, and UI colors are centralized here.
"""

import os

# --- Application Info ---
APP_NAME = "Nova DSO Tracker"
APP_VERSION = "1.2.9-beta.1"

# --- Docker Configuration ---
DOCKER_IMAGE = "mrantonsg/nova-dso-tracker"
DOCKER_TAG = "latest"
DOCKER_IMAGE_FULL = f"{DOCKER_IMAGE}:{DOCKER_TAG}"
DOCKER_CONTAINER_NAME = "nova-tracker"
COMPOSE_FILENAME = "docker-compose.yml"

# --- Network Configuration ---
PORT = 5001
DASHBOARD_URL = f"http://localhost:{PORT}"

# --- Docker Hub API ---
DOCKER_HUB_API = f"https://hub.docker.com/v2/repositories/{DOCKER_IMAGE.replace('/', '%2F')}/tags/{DOCKER_TAG}"

# --- Docker Download ---
DOCKER_DOWNLOAD_URL = "https://www.docker.com/products/docker-desktop"

# --- GitHub (Launcher Self-Update) ---
GITHUB_REPO = "mrantonsg/nova-dso-tracker-launcher"
GITHUB_RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# --- Paths ---
# Install directory: ~/nova (Universal & Safe)
NOVA_DIR = os.path.join(os.path.expanduser("~"), "nova")
INSTANCE_DIR = os.path.join(NOVA_DIR, "instance")
COMPOSE_FILE = os.path.join(NOVA_DIR, COMPOSE_FILENAME)
LAUNCHER_PREFS_FILE = os.path.join(NOVA_DIR, ".launcher_prefs.json")

# --- Docker Compose Template ---
COMPOSE_TEMPLATE = f"""services:
  tracker:
    image: {DOCKER_IMAGE_FULL}
    container_name: {DOCKER_CONTAINER_NAME}
    ports:
      - "{PORT}:{PORT}"
    volumes:
      - ./instance:/app/instance
    restart: unless-stopped"""

# --- Timeouts and Poll Intervals (in seconds) ---
DOCKER_CMD_TIMEOUT = 300      # Default timeout for Docker commands
DOCKER_INFO_TIMEOUT = 10      # Timeout for `docker info` checks
CONTAINER_START_POLL_COUNT = 30   # Max polls for container to reach "Up" state
DOCKER_START_POLL_COUNT = 60      # Max polls for Docker daemon to become ready
WEB_READY_TIMEOUT = 2.0       # Timeout for HTTP check on dashboard
MONITOR_INTERVAL = 3          # Seconds between state checks
UPDATE_BANNER_DISPLAY_TIME = 3    # Seconds to show "Update Applied" message

# --- Colors (for UI theming) ---
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
