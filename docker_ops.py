# -*- coding: utf-8 -*-
"""
Docker operations for Nova DSO Tracker Launcher.

Handles all Docker-related commands, container management, image versioning,
and Docker Hub API interactions.
"""

import json
import os
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request
import urllib.error
from typing import Optional, Tuple, Dict, Any

import certifi

# SSL context for HTTPS requests (uses certifi's bundled certificates)
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def _subprocess_flags() -> int:
    """Return CREATE_NO_WINDOW flag on Windows to prevent console flashing."""
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0

from config import (
    DOCKER_IMAGE,
    DOCKER_IMAGE_FULL,
    DOCKER_TAG,
    DOCKER_CONTAINER_NAME,
    COMPOSE_FILE,
    COMPOSE_TEMPLATE,
    DOCKER_CMD_TIMEOUT,
    DOCKER_INFO_TIMEOUT,
    DOCKER_HUB_API,
    LAUNCHER_PREFS_FILE,
    NOVA_DIR,
    CONTAINER_START_POLL_COUNT,
)
from utils import sanitize_for_shell


def run_command(
    args: list,
    cwd: Optional[str] = None,
    timeout: int = DOCKER_CMD_TIMEOUT,
    env: Optional[dict] = None,
) -> Tuple[str, str, int]:
    """
    Run a command using subprocess without shell=True for security.

    Args:
        args: List of command arguments (e.g., ["docker", "info"])
        cwd: Working directory for the command
        timeout: Timeout in seconds
        env: Environment variables (defaults to os.environ)

    Returns:
        Tuple of (stdout, stderr, return_code)
    """
    if env is None:
        env = os.environ.copy()

    # Add platform-specific paths for Docker
    if os.name != "nt":  # Unix-like systems
        env["PATH"] = env.get("PATH", "")
        if sys_platform() == "darwin":
            env["PATH"] += os.pathsep + "/usr/local/bin" + os.pathsep + "/opt/homebrew/bin"
        elif sys_platform() == "linux":
            env["PATH"] += os.pathsep + "/usr/local/bin" + os.pathsep + "/snap/bin"

    try:
        result = subprocess.run(
            args,
            cwd=cwd or NOVA_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_subprocess_flags(),
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", f"Command timed out after {timeout}s", -1
    except FileNotFoundError:
        return "", f"Command not found: {args[0]}", -1
    except Exception as e:
        return "", str(e), -1


def sys_platform() -> str:
    """Get the platform identifier."""
    import sys
    return sys.platform


def is_docker_installed() -> bool:
    """
    Check if Docker is installed on the system.

    Returns:
        True if Docker binary is found in PATH
    """
    return shutil.which("docker") is not None


def is_docker_running() -> Tuple[bool, str]:
    """
    Check if the Docker daemon is running.

    Returns:
        Tuple of (is_running: bool, status_message: str)
        status_message is one of: "running", "stopped", "missing", "error"
    """
    if not is_docker_installed():
        return False, "missing"

    stdout, stderr, rc = run_command(
        ["docker", "info"],
        timeout=DOCKER_INFO_TIMEOUT,
    )

    if "Server Version" in stdout:
        return True, "running"

    # Distinguish "not running" from "not properly installed"
    if rc != 0 and (
        "connect" not in stderr.lower()
        and "daemon" not in stderr.lower()
        and "is the docker daemon running" not in stderr.lower()
    ):
        return False, "missing"

    return False, "stopped"


def is_nova_installed() -> bool:
    """
    Check if Nova DSO Tracker is installed (docker-compose.yml exists).

    Returns:
        True if docker-compose.yml exists in NOVA_DIR
    """
    return os.path.exists(COMPOSE_FILE)


def is_container_running() -> Tuple[bool, str]:
    """
    Check if the Nova container is currently running.

    Returns:
        Tuple of (is_running: bool, status_string: str)
        status_string contains the docker ps status output
    """
    stdout, stderr, rc = run_command(
        [
            "docker", "ps",
            "--filter", f"name={DOCKER_CONTAINER_NAME}",
            "--format", "{{.Status}}",
        ],
        timeout=DOCKER_INFO_TIMEOUT,
    )

    if "Up" in stdout:
        return True, stdout
    return False, stdout


def create_compose_file() -> bool:
    """
    Create the docker-compose.yml file in NOVA_DIR.

    Returns:
        True if file was created successfully
    """
    try:
        os.makedirs(NOVA_DIR, exist_ok=True)
        with open(COMPOSE_FILE, "w") as f:
            f.write(COMPOSE_TEMPLATE)
        return True
    except (PermissionError, OSError):
        return False


def pull_image(callback=None) -> Tuple[bool, str]:
    """
    Pull the latest Docker image.

    Args:
        callback: Optional callback function to receive progress updates

    Returns:
        Tuple of (success: bool, message: str)
    """
    stdout, stderr, rc = run_command(
        ["docker", "pull", DOCKER_IMAGE_FULL],
        timeout=DOCKER_CMD_TIMEOUT,
    )

    if rc == 0:
        return True, "Image pulled successfully"
    return False, stderr or "Failed to pull image"


def start_container(callback=None) -> Tuple[bool, str]:
    """
    Start the Nova container using docker compose.

    Returns:
        Tuple of (success: bool, message: str)
    """
    # First ensure compose file exists
    if not is_nova_installed():
        if not create_compose_file():
            return False, "Failed to create docker-compose.yml"

    # Use explicit -f flag for Windows compatibility
    stdout, stderr, rc = run_command(
        ["docker", "compose", "-f", COMPOSE_FILE, "up", "-d"],
        timeout=DOCKER_CMD_TIMEOUT,
    )

    if rc != 0:
        return False, stderr or "Failed to start container"

    # Poll until container is "Up"
    for _ in range(CONTAINER_START_POLL_COUNT):
        is_running, _ = is_container_running()
        if is_running:
            return True, "Container started successfully"
        time.sleep(1)

    return False, "Container did not start within expected time"


def stop_container() -> Tuple[bool, str]:
    """
    Stop the Nova container using docker compose.

    Returns:
        Tuple of (success: bool, message: str)
    """
    # Use explicit -f flag for Windows compatibility
    stdout, stderr, rc = run_command(
        ["docker", "compose", "-f", COMPOSE_FILE, "stop"],
        timeout=DOCKER_CMD_TIMEOUT,
    )

    if rc == 0:
        return True, "Container stopped successfully"
    return False, stderr or "Failed to stop container"


def recreate_container() -> Tuple[bool, str]:
    """
    Force recreate the container (used after image update).

    Returns:
        Tuple of (success: bool, message: str)
    """
    # Use explicit -f flag for Windows compatibility
    stdout, stderr, rc = run_command(
        ["docker", "compose", "-f", COMPOSE_FILE, "up", "-d", "--force-recreate"],
        timeout=DOCKER_CMD_TIMEOUT,
    )

    if rc == 0:
        return True, "Container recreated successfully"
    return False, stderr or "Failed to recreate container"


def get_local_image_digest() -> Optional[str]:
    """
    Get the registry digest of the locally pulled image.

    Uses .RepoDigests which contains the actual registry digest that was
    saved when the image was pulled. This is different from .Id which is
    the image config digest.

    Returns:
        The registry digest (sha256 hash) or None if not found
    """
    stdout, stderr, rc = run_command(
        [
            "docker", "image", "inspect",
            DOCKER_IMAGE_FULL,
            "--format", "{{index .RepoDigests 0}}",
        ],
        timeout=DOCKER_INFO_TIMEOUT,
    )

    if rc == 0 and stdout:
        # RepoDigests format is "image@sha256:abc123..." - extract just the digest
        if "@" in stdout:
            return stdout.split("@")[1]
        # Fallback: if format is unexpected, return as-is
        if stdout.startswith("sha256:"):
            return stdout
        return f"sha256:{stdout}" if len(stdout) >= 12 else stdout
    return None


def get_container_image_digest() -> Optional[str]:
    """
    Get the digest of the image used by the running container.

    Returns:
        The image digest (short form) or None if not found
    """
    stdout, stderr, rc = run_command(
        [
            "docker", "inspect",
            "--format", "{{.Image}}",
            DOCKER_CONTAINER_NAME,
        ],
        timeout=DOCKER_INFO_TIMEOUT,
    )

    if stdout and "sha256:" in stdout:
        return stdout.replace("sha256:", "")[:12]
    return None


def check_dockerhub_version() -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check Docker Hub for the latest image version and compare with local.

    Uses docker manifest inspect to get the remote digest, which is more reliable
    than the Docker Hub API for public images.

    Returns:
        Tuple of (update_available: bool, remote_digest: str|None, error: str|None)
        - update_available: True if remote image is different from local
        - remote_digest: The digest from Docker Hub, or None on error
        - error: Error message if the check failed, None otherwise
    """
    try:
        # Method 1: Use docker manifest inspect (most reliable when Docker is running)
        stdout, stderr, rc = run_command(
            ["docker", "manifest", "inspect", DOCKER_IMAGE_FULL, "--verbose"],
            timeout=DOCKER_INFO_TIMEOUT,
        )

        if rc == 0 and stdout:
            # Parse the manifest output to get the digest
            # The output is JSON when using --verbose
            try:
                data = json.loads(stdout)
                # The structure varies, try to find the digest
                remote_digest = None

                # Try different locations in the JSON structure
                if isinstance(data, dict):
                    # Direct digest field
                    remote_digest = data.get("digest") or data.get("Descriptor", {}).get("digest")

                    # Try manifest list
                    if not remote_digest and "manifests" in data:
                        for manifest in data["manifests"]:
                            if manifest.get("platform", {}).get("architecture") in ["amd64", "arm64"]:
                                remote_digest = manifest.get("digest")
                                break

                    # Try schema 2 manifest
                    if not remote_digest and "manifest" in data:
                        remote_digest = data["manifest"].get("config", {}).get("digest")

                if remote_digest:
                    return _compare_digests(remote_digest)
            except json.JSONDecodeError:
                pass

        # Method 2: Fall back to Docker Hub API
        namespace, repo = DOCKER_IMAGE.split("/")
        api_url = f"https://hub.docker.com/v2/repositories/{namespace}/{repo}/tags/{DOCKER_TAG}"

        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": "NovaLauncher/1.0"},
        )

        try:
            with urllib.request.urlopen(req, timeout=10, context=_SSL_CONTEXT) as response:
                data = json.loads(response.read().decode())

                # Get the digest from Docker Hub response
                remote_digest = data.get("digest")

                if not remote_digest:
                    # Try alternate field names
                    images = data.get("images", [])
                    if images and len(images) > 0:
                        remote_digest = images[0].get("digest")

                if not remote_digest:
                    return False, None, "Could not find digest in Docker Hub response"

                return _compare_digests(remote_digest)

        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False, None, f"Image not found on Docker Hub: {DOCKER_IMAGE_FULL}"
            return False, None, f"Docker Hub API error: {e.code}"
        except urllib.error.URLError as e:
            return False, None, f"Network error: {e.reason}"

    except Exception as e:
        return False, None, str(e)


def _compare_digests(remote_digest: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Compare a remote digest with the local image digest.

    Args:
        remote_digest: The digest from Docker Hub or manifest inspect

    Returns:
        Tuple of (update_available, remote_digest, error)
    """
    local_digest = get_local_image_digest()

    if local_digest is None:
        # No local image, update available
        return True, remote_digest, None

    # Normalize digests for comparison
    remote_normalized = remote_digest.replace("sha256:", "").lower()
    local_normalized = local_digest.replace("sha256:", "").lower()

    # Compare first 64 chars (full SHA256)
    update_available = remote_normalized[:64] != local_normalized[:64]

    return update_available, remote_digest, None


def prune_images() -> Tuple[bool, str]:
    """
    Remove unused Docker images to free disk space.

    Returns:
        Tuple of (success: bool, message: str)
    """
    stdout, stderr, rc = run_command(
        ["docker", "image", "prune", "-f"],
        timeout=DOCKER_CMD_TIMEOUT,
    )

    if rc == 0:
        return True, "Images pruned successfully"
    return False, stderr or "Failed to prune images"


# --- Launcher Preferences ---

def load_launcher_prefs() -> Dict[str, Any]:
    """
    Load launcher preferences from the JSON file.

    Returns:
        Dictionary of preferences (empty dict if file doesn't exist)
    """
    try:
        if os.path.exists(LAUNCHER_PREFS_FILE):
            with open(LAUNCHER_PREFS_FILE, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, PermissionError, OSError):
        pass
    return {}


def save_launcher_prefs(prefs: Dict[str, Any]) -> bool:
    """
    Save launcher preferences to the JSON file.

    Args:
        prefs: Dictionary of preferences to save

    Returns:
        True if saved successfully
    """
    try:
        os.makedirs(NOVA_DIR, exist_ok=True)
        with open(LAUNCHER_PREFS_FILE, "w") as f:
            json.dump(prefs, f, indent=2)
        return True
    except (PermissionError, OSError):
        return False


def get_skipped_digest() -> Optional[str]:
    """
    Get the digest of the version the user has chosen to skip.

    Returns:
        The skipped digest or None
    """
    prefs = load_launcher_prefs()
    return prefs.get("skipped_digest")


def set_skipped_digest(digest: str) -> bool:
    """
    Save the digest of a version the user wants to skip.

    Args:
        digest: The image digest to skip

    Returns:
        True if saved successfully
    """
    prefs = load_launcher_prefs()
    prefs["skipped_digest"] = digest
    return save_launcher_prefs(prefs)


def clear_skipped_digest() -> bool:
    """
    Clear the skipped digest preference.

    Returns:
        True if cleared successfully
    """
    prefs = load_launcher_prefs()
    if "skipped_digest" in prefs:
        del prefs["skipped_digest"]
        return save_launcher_prefs(prefs)
    return True
