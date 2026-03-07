#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Windows .ico file from PNG source.

This script converts nova_logo.png to nova_logo.ico for Windows builds.
Run this before building the Windows executable.

Requirements:
    pip install Pillow

Usage:
    python generate_icons.py
"""

import os
import sys

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)


def generate_ico(png_path: str, ico_path: str) -> bool:
    """
    Generate a multi-resolution .ico file from a PNG.

    Args:
        png_path: Path to source PNG file
        ico_path: Path to output .ico file

    Returns:
        True if successful
    """
    try:
        # Open the source image
        img = Image.open(png_path)

        # Convert to RGBA if necessary
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Generate multiple sizes for the ico file
        # Windows uses these sizes: 16, 32, 48, 64, 128, 256
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

        icons = []
        for size in sizes:
            resized = img.resize(size, Image.Resampling.LANCZOS)
            icons.append(resized)

        # Save as ico with all sizes
        icons[0].save(
            ico_path,
            format="ICO",
            sizes=sizes,
            append_images=icons[1:],
        )

        print(f"Generated: {ico_path}")
        return True

    except FileNotFoundError:
        print(f"Error: Source file not found: {png_path}")
        return False
    except Exception as e:
        print(f"Error generating ico: {e}")
        return False


def main():
    # Get the directory containing this script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    png_path = os.path.join(script_dir, "nova_logo.png")
    ico_path = os.path.join(script_dir, "nova_logo.ico")

    print(f"Source: {png_path}")
    print(f"Target: {ico_path}")

    if not os.path.exists(png_path):
        print(f"Error: PNG file not found: {png_path}")
        sys.exit(1)

    if generate_ico(png_path, ico_path):
        print("Success!")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
