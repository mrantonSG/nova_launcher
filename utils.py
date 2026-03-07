# -*- coding: utf-8 -*-
"""
Utility functions for Nova DSO Tracker Launcher.

Includes resource path handling, web readiness checks, and version comparison.
"""

import os
import sys
import urllib.request
import urllib.error

from config import DASHBOARD_URL, WEB_READY_TIMEOUT


def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and for PyInstaller.

    Args:
        relative_path: Path relative to the application root

    Returns:
        Absolute path to the resource
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except (AttributeError, Exception):
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def check_web_ready() -> bool:
    """
    Check if the Nova dashboard is responsive.

    Returns:
        True if the dashboard returns a valid HTTP 200 response with content
    """
    try:
        with urllib.request.urlopen(DASHBOARD_URL, timeout=WEB_READY_TIMEOUT) as response:
            if response.getcode() != 200:
                return False
            content = response.read()
            return len(content) > 500
    except Exception:
        return False


def version_newer(remote: str, local: str) -> bool:
    """
    Compare semver strings.

    Args:
        remote: Remote version string (e.g., "1.2.3")
        local: Local version string (e.g., "1.2.0")

    Returns:
        True if remote version is greater than local version
    """
    try:
        r_parts = tuple(int(x) for x in remote.split("."))
        l_parts = tuple(int(x) for x in local.split("."))

        # Pad shorter version with zeros for proper comparison
        max_len = max(len(r_parts), len(l_parts))
        r_padded = r_parts + (0,) * (max_len - len(r_parts))
        l_padded = l_parts + (0,) * (max_len - len(l_parts))

        return r_padded > l_padded
    except (ValueError, AttributeError):
        return False


def sanitize_for_shell(value: str) -> str:
    """
    Sanitize a string value to prevent shell injection.

    This is a safety measure for values that might be interpolated into
    command strings. For maximum safety, prefer using list-based subprocess
    calls instead of shell=True.

    Args:
        value: String to sanitize

    Returns:
        Sanitized string safe for shell interpolation
    """
    # Remove any characters that could be used for injection
    # Keep only alphanumeric, dash, underscore, dot, forward slash, and colon
    allowed_chars = set(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        "-_./:"
    )
    return "".join(c for c in value if c in allowed_chars)
