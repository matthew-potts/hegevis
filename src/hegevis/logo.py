"""The masthead mark, on every chart that leaves the building.

This is furniture, not decoration, and it is deliberately not a parameter.
A chart is republished, screenshotted and pasted into decks far from the
article it was drawn for, and the mark is what still says where it came from
once the page around it is gone. Making it optional means it is missing exactly
on the charts that travel furthest, so the package stamps it rather than
trusting each analyst to remember.

Placement follows the furniture already in :mod:`hegevis.layout`: the title
hangs off the left margin at the top, and the mark hangs off the right margin
at the foot, on the same optical inset from the trim as the source line. It is
sized in millimetres rather than as a fraction of the figure, so it is the same
physical mark on a single-column chart and a full-page one.

The art desk changes it in one place -- the ``[logo]`` block of the theme file.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import matplotlib.image as mpimg

from .theme import MM, Theme, get_theme

PACKAGED = Path(__file__).parent / "assets" / "hegemon_logo.png"

# Stamping is idempotent: finish() and save() both assert the mark, because a
# figure can reach the page through either. The axes is tagged so a second call
# recognises its own work instead of stacking a third copy on the second.
AXES_LABEL = "hegevis-logo"


class MissingLogo(FileNotFoundError):
    """The theme names a logo file that is not there."""


def resolve_path(theme: Theme | None = None) -> Path:
    """Which file the mark is drawn from.

    A theme may override the packaged asset with ``[logo] path``. A relative
    path is read against the theme file's own directory, so a section theme can
    sit next to its logo and travel with it.
    """
    t = theme or get_theme()
    if not t.logo.path:
        return PACKAGED
    p = Path(t.logo.path).expanduser()
    if not p.is_absolute() and t.source_path is not None:
        p = t.source_path.parent / p
    if not p.is_file():
        raise MissingLogo(
            f"[logo] path in {getattr(t.source_path, 'name', 'the theme')} points at "
            f"{p}, which does not exist. Every chart carries the mark, so this is "
            "not something the package can skip past."
        )
    return p


@lru_cache(maxsize=8)
def _read(path: str, mtime: float):
    """Decode once per file. ``mtime`` is in the key so editing it re-reads."""
    return mpimg.imread(path)


def image(theme: Theme | None = None):
    """The mark as an RGBA array."""
    p = resolve_path(theme)
    return _read(str(p), p.stat().st_mtime)


def size_in(theme: Theme | None = None) -> tuple[float, float]:
    """``(width, height)`` of the mark in inches, at the theme's height."""
    t = theme or get_theme()
    h_px, w_px = image(t).shape[:2]
    h_in = t.logo.height_mm * MM
    return h_in * (w_px / h_px), h_in


def reserved_bottom_in(theme: Theme | None = None) -> float:
    """How much of the foot the mark occupies, measured from the trim."""
    t = theme or get_theme()
    return t.logo.inset_mm * MM + size_in(t)[1]


def stamp(fig, theme: Theme | None = None):
    """Draw the mark bottom-right. Returns the axes it lives in.

    Safe to call repeatedly -- a figure that already carries the mark is left
    alone, so ``finish()`` and ``save()`` can both insist on it.
    """
    t = theme or get_theme()
    for ax in fig.axes:
        if ax.get_label() == AXES_LABEL:
            return ax

    w_in, h_in = size_in(t)
    fig_w, fig_h = fig.get_size_inches()
    # Right edge on the right margin, so the mark shares a measure with the
    # title and source line; bottom edge on the same trim inset as the footer.
    left_in = fig_w - t.layout.margin.right * MM - w_in
    bottom_in = t.logo.inset_mm * MM

    ax = fig.add_axes(
        [left_in / fig_w, bottom_in / fig_h, w_in / fig_w, h_in / fig_h],
        label=AXES_LABEL, zorder=6,
    )
    # interpolation="none" is what keeps the original pixels in the PDF: any
    # other setting has matplotlib resample the mark down to screen resolution
    # on the way out, and a 700dpi logo becomes a 70dpi one on press.
    ax.imshow(image(t), interpolation="none", resample=False)
    ax.set_axis_off()
    ax.patch.set_visible(False)
    ax.set_in_layout(False)  # never let a tight/constrained layout move it
    return ax


def has_logo(fig) -> bool:
    return any(ax.get_label() == AXES_LABEL for ax in fig.axes)


def is_logo_axes(ax) -> bool:
    """For code that walks a figure's axes and should skip the furniture."""
    return ax.get_label() == AXES_LABEL
