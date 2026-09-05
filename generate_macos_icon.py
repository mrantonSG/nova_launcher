#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a macOS-style (squircle) source icon from the Nova logo.

Since Big Sur, macOS no longer auto-masks app icons into the rounded
"squircle" shape -- that shape and the internal padding have to be baked
into the source artwork itself. nova_logo.png is a flat, edge-to-edge
square, which is why the Dock icon currently looks like a plain square
tile instead of a proper macOS icon.

This script does NOT touch nova_logo.png. It produces a new source file,
nova_logo_macos.png, which:
  - is a 1024x1024 canvas
  - has the logo's background color filling the canvas edge-to-edge, but
    the *glyph* (the "N" mark) padded inward by roughly 10% per side, so
    it doesn't crowd the icon's rounded corners
  - is clipped to a superellipse ("squircle": |x|^n + |y|^n <= r^n with a
    high exponent n) rather than a plain rounded-rectangle, which is a
    much closer match to how real macOS icons are shaped

Source resolution note:
    nova_logo.png itself is only 70x70px. Upscaling that ~14.6x to fill a
    1024px canvas would look visibly soft/blurry. nova_logo.icns already
    contains the exact same artwork natively rendered at 1024x1024 (Pillow's
    ICNS reader picks the largest representation automatically), so this
    script sources from nova_logo.icns for a crisp result. Both files render
    the identical logo -- this only affects sharpness, not content.

Usage:
    python generate_macos_icon.py
"""

import os
import sys

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

# --- Tunable parameters -----------------------------------------------

CANVAS_SIZE = 1024          # output canvas, px (square)
PADDING_FRACTION = 0.10     # padding on each side, as a fraction of canvas size
SUPERELLIPSE_EXPONENT = 5   # higher = closer to a rounded-rect; lower = closer to a circle
MASK_SUPERSAMPLE = 4        # render the mask at this multiple, then downsample, for anti-aliasing
BACKGROUND_RGBA = (255, 255, 255, 255)  # matches the logo's own background color

# ------------------------------------------------------------------------


def build_squircle_mask(size: int, exponent: int, supersample: int) -> Image.Image:
    """Build an anti-aliased superellipse alpha mask, sized (size, size)."""
    hi_res = size * supersample
    radius = hi_res / 2.0

    # Vectorized superellipse evaluation via numpy for speed.
    import numpy as np

    ys, xs = np.mgrid[0:hi_res, 0:hi_res].astype(np.float64)
    xs = xs - radius + 0.5
    ys = ys - radius + 0.5

    value = (np.abs(xs) / radius) ** exponent + (np.abs(ys) / radius) ** exponent
    inside = value <= 1.0

    mask_hi = (inside.astype(np.uint8)) * 255
    mask_img = Image.fromarray(mask_hi, mode="L")
    return mask_img.resize((size, size), Image.Resampling.LANCZOS)


def generate_macos_icon(source_path: str, output_path: str) -> bool:
    try:
        source = Image.open(source_path)
    except FileNotFoundError:
        print(f"Error: source file not found: {source_path}")
        return False

    if source.mode != "RGBA":
        source = source.convert("RGBA")

    # 1. Full-bleed background canvas, matching the logo's own background color,
    #    so the resized glyph blends into it seamlessly (no visible seam).
    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), BACKGROUND_RGBA)

    # 2. Resize the whole source (glyph + its background) down into the padded
    #    inner area and paste it centered. Because the source's background
    #    matches BACKGROUND_RGBA, only the glyph itself reads as "padded" --
    #    the background stays flush to the canvas edges.
    inner_size = round(CANVAS_SIZE * (1 - 2 * PADDING_FRACTION))
    resized = source.resize((inner_size, inner_size), Image.Resampling.LANCZOS)
    offset = (CANVAS_SIZE - inner_size) // 2
    canvas.paste(resized, (offset, offset), resized)

    # 3. Clip the canvas to a superellipse ("squircle") mask.
    mask = build_squircle_mask(CANVAS_SIZE, SUPERELLIPSE_EXPONENT, MASK_SUPERSAMPLE)
    r, g, b, a = canvas.split()
    a = Image.composite(a, Image.new("L", (CANVAS_SIZE, CANVAS_SIZE), 0), mask)
    # Also cut RGB alpha where the source itself had transparency (not the case
    # here, since the logo is fully opaque, but keeps this correct in general).
    final = Image.merge("RGBA", (r, g, b, a))

    final.save(output_path, format="PNG")
    print(f"Generated: {output_path} ({final.size[0]}x{final.size[1]})")
    return True


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Prefer the 1024x1024 artwork embedded in nova_logo.icns over the 70x70
    # nova_logo.png -- see the module docstring for why.
    icns_path = os.path.join(script_dir, "nova_logo.icns")
    png_path = os.path.join(script_dir, "nova_logo.png")
    source_path = icns_path if os.path.exists(icns_path) else png_path

    output_path = os.path.join(script_dir, "nova_logo_macos.png")

    print(f"Source: {source_path}")
    print(f"Target: {output_path}")
    print(
        f"Padding: {PADDING_FRACTION * 100:.0f}% per side "
        f"(inner area: {round(CANVAS_SIZE * (1 - 2 * PADDING_FRACTION))}x"
        f"{round(CANVAS_SIZE * (1 - 2 * PADDING_FRACTION))} of {CANVAS_SIZE}x{CANVAS_SIZE})"
    )
    print(f"Squircle exponent: {SUPERELLIPSE_EXPONENT}")

    if generate_macos_icon(source_path, output_path):
        print("Success!")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
