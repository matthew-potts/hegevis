"""Derive the print asset ``hegemon_logo.png`` from the supplied JPEG.

The logo arrives as a JPEG, which cannot carry transparency, so the artwork
sits on a white field. White is not the chart's ground -- the house surface is
the cover cream (#f5f1e7) -- so dropping the JPEG straight onto a figure paints
a white square and a white rim around the rounded tile, both plainly visible in
print. This script knocks the white out to alpha and crops to the mark, so the
logo sits on whatever surface the theme defines.

The rounded corners are anti-aliased, so a hard threshold would leave them
jagged. Every edge pixel is a blend of the tile colour over white, which we can
undo exactly: recover the coverage from how far the pixel travelled away from
white, then un-premultiply to get the tile colour back.

Run after replacing the JPEG:

    python tools/make_logo_asset.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

ASSETS = Path(__file__).resolve().parent.parent / "src" / "hegevis" / "assets"
SOURCE = ASSETS / "hegemon_logo.jpeg"
TARGET = ASSETS / "hegemon_logo.png"

# The tile's own sand -- the colour the anti-aliased rim is blending toward.
# Coverage is measured against its distance from white.
TILE = np.array([247, 214, 135], dtype=float)

# JPEG ringing leaves a faint halo of not-quite-white pixels around the tile.
# Left alone it becomes a ghost of sand floating on the cream, so anything
# under this coverage is treated as field rather than mark.
NOISE_FLOOR = 0.12
SOLID = 0.5  # the coverage that marks the true edge, for the crop


def knockout(rgb: np.ndarray) -> np.ndarray:
    """White field -> alpha, with the anti-aliased rim reconstructed."""
    white = np.array([255.0, 255.0, 255.0])
    # How far this pixel sits from white, as a fraction of how far the tile
    # sits from white. Interior pixels clip to 1; the rim lands in between.
    reach = np.linalg.norm(white - TILE)
    alpha = np.clip(np.linalg.norm(white - rgb, axis=-1) / reach, 0.0, 1.0)
    alpha = np.clip((alpha - NOISE_FLOOR) / (1 - NOISE_FLOOR), 0.0, 1.0)

    # Undo `observed = a * colour + (1 - a) * white` to recover the colour.
    a = alpha[..., None]
    colour = np.where(a > 0, (rgb - (1 - a) * white) / np.where(a > 0, a, 1), white)
    return np.dstack([np.clip(colour, 0, 255), alpha * 255]).astype(np.uint8)


def crop_box(alpha: np.ndarray) -> tuple[int, int, int, int]:
    """Bounds of the mark, taken at half coverage and grown to keep the rim.

    ``Image.getbbox`` would anchor on the faintest surviving pixel, which is
    ringing rather than artwork. Half coverage is where the edge actually is.
    """
    rows, cols = np.nonzero(alpha >= SOLID * 255)
    h, w = alpha.shape
    return (max(int(cols.min()) - 1, 0), max(int(rows.min()) - 1, 0),
            min(int(cols.max()) + 2, w), min(int(rows.max()) + 2, h))


def main() -> int:
    rgba = knockout(np.asarray(Image.open(SOURCE).convert("RGB"), dtype=float))
    # Crop the transparent padding: the theme's height_mm should measure the
    # mark itself, not the whitespace the JPEG happened to ship with.
    box = crop_box(rgba[..., 3])
    out = Image.fromarray(rgba, mode="RGBA").crop(box)
    out.save(TARGET, optimize=True)
    print(f"wrote {TARGET.relative_to(Path.cwd())} {out.size[0]}x{out.size[1]} from {box}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
