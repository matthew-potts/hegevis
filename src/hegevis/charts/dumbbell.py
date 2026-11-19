"""The dumbbell: two values per row, joined, on one shared value axis.

The bar-chart answer to "how far did each one move". It is a ranked chart that
marks two points instead of one length -- the rows, left-hand names and value
axis are the same as :func:`ranked`, so the two read as one family. Use it
over :func:`slope` when the levels matter as much as the change, or when there
are too many rows for a slope chart's labels to stay apart.

Colour encodes the period, not the row: the earlier dot is the neutral grey
and the later one the lead hue, so the eye lands on where things ended up.
"""

from __future__ import annotations

import numpy as np

from ..palette import default_palette
from ..rc import LINE_PT
from ..theme import get_theme
from .bars import _cap_slots, _fmt, _reserve_left_for

DOT_PT = 5.0          # marker diameter
KEY_PAD_PT = 4.0      # gap between the top row's dots and their period labels


def dumbbell(ax, data, *, labels=None, palette=None, color=None, theme=None,
             sort=True, unit="", label_values=False):
    """One row per name: a dot at each of two values, joined by a rule.

    ``data`` maps each name to its ``(start, end)`` pair. ``labels`` names the
    two periods; it defaults to "Before" and "After". They are written once,
    above the top row's dots, rather than in a legend.

    Rows are ordered by their end value, largest at the top, unless
    ``sort=False`` -- then they keep the order given, top to bottom.
    """
    t = theme or get_theme()
    pal = palette or default_palette(t)
    pairs = {str(k): tuple(float(x) for x in v) for k, v in dict(data).items()}
    if not pairs:
        raise ValueError("dumbbell() needs at least one row")
    bad = [k for k, v in pairs.items() if len(v) != 2]
    if bad:
        raise ValueError(f"dumbbell() takes exactly two values per row - {bad} did not")
    periods = list(labels) if labels else ["Before", "After"]
    if len(periods) != 2:
        raise ValueError("dumbbell() labels must name exactly two periods")

    names = list(pairs)
    if sort:
        names.sort(key=lambda n: pairs[n][1])
    else:
        names.reverse()  # barh-style: position 0 is the bottom row
    pos = np.arange(len(names))
    starts = np.array([pairs[n][0] for n in names])
    ends = np.array([pairs[n][1] for n in names])
    c_start, c_end = t.neutral, color or pal.slot(0)

    _cap_slots(ax, len(names), "y")
    ax.hlines(pos, starts, ends, color=t.neutral, alpha=0.5,
              linewidth=LINE_PT, zorder=2)
    for xs, c in ((starts, c_start), (ends, c_end)):
        ax.plot(xs, pos, linestyle="none", marker="o", markersize=DOT_PT,
                markeredgewidth=0, color=c, zorder=3)

    ax.set_yticks(pos, names)
    ax.tick_params(axis="y", length=0, labelleft=True, labelright=False)
    _reserve_left_for(ax, names, t)
    ax.grid(axis="x", visible=True)
    ax.grid(axis="y", visible=False)
    ax.set_axisbelow(True)

    # The key sits on the top row, each period named over its own dot and in
    # its colour -- the reader learns the encoding where the data is.
    top = len(names) - 1
    for x, text, c in ((starts[top], periods[0], c_start),
                       (ends[top], periods[1], c_end)):
        ax.annotate(text, xy=(x, top), xytext=(0, DOT_PT / 2 + KEY_PAD_PT),
                    textcoords="offset points", ha="center", va="bottom",
                    fontsize=t.size.body, color=c, fontweight=t.weight_medium,
                    zorder=4, annotation_clip=False)

    if label_values:
        for p, a, b in zip(pos, starts, ends):
            lo, hi = sorted((a, b))
            for x, ha, sign in ((lo, "right", -1), (hi, "left", 1)):
                ax.annotate(_fmt(x, unit), xy=(x, p),
                            xytext=(sign * (DOT_PT / 2 + 3), 0),
                            textcoords="offset points", ha=ha, va="center",
                            fontsize=t.size.body, color=t.ink_soft, zorder=4,
                            annotation_clip=False)
    return ax
