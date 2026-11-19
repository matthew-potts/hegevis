"""The timeline: dated milestones down a rule, each a headline number.

For a run of facts that share a story but not a unit -- satellites launched,
revenue, subscribers -- where any value axis would be a lie. The dates carry
the order, the numbers carry the weight, and nothing is plotted to scale.

Vertical, because a single column is narrow and dates are short while
descriptions are long: a horizontal timeline at 88mm leaves each milestone a
sliver of width and forces every description onto four lines.

Milestones are evenly spaced, not placed to scale in time. A to-scale axis
would crush the recent, dense end of most stories into a single point.
"""

from __future__ import annotations

import warnings
from itertools import groupby

from ..palette import default_palette
from ..rc import LINE_PT
from ..theme import get_theme
from .timeseries import _get_renderer

DOT_PT = 5.0
GAP_PT = 6.0          # between the date, rule, value and description columns
GROUP_GAP = 0.9       # extra space between dates, in value-line heights
TOP_PAD_PT = 8.0      # clear air between the subtitle and the first milestone


def _text_px(ax, s, renderer, **kw) -> float:
    probe = ax.text(0, 0, s, **kw)
    w = probe.get_window_extent(renderer=renderer).width
    probe.remove()
    return w


def _wrap(ax, text, width_px, renderer, **kw) -> list[str]:
    """Greedy word wrap, measured in the real font rather than by characters."""
    lines, line = [], ""
    for word in str(text).split():
        trial = f"{line} {word}".strip()
        if line and _text_px(ax, trial, renderer, **kw) > width_px:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + ([line] if line else [])


def timeline(ax, events, *, palette=None, color=None, theme=None):
    """Dated milestones as a vertical timeline.

    ``events`` is a sequence of ``(date, value, description)`` -- all text, in
    the order they should read, top to bottom. Consecutive events with the same
    date share one date label and one dot. ``value`` is set large ("10,790",
    "$11.4bn"); ``description`` sits beside it and wraps to fit.

    The axes are used as a canvas: no scale, no gridlines. Size the figure to
    the content -- if the milestones do not fit the box a warning says so.
    """
    t = theme or get_theme()
    pal = palette or default_palette(t)
    events = [(str(d), str(v), str(s)) for d, v, s in events]
    if not events:
        raise ValueError("timeline() needs at least one event")

    fig = ax.figure
    renderer = _get_renderer(fig)
    px_per_pt = fig.dpi / 72
    box = ax.get_window_extent(renderer=renderer)
    w_pt, h_pt = box.width / px_per_pt, box.height / px_per_pt

    date_kw = dict(fontsize=t.size.body, fontweight=t.weight_medium)
    value_kw = dict(fontsize=t.size.subtitle, fontfamily=list(t.titles))
    desc_kw = dict(fontsize=t.size.body)

    # Columns, in points from the left of the box: dates right-aligned to the
    # rule, then the values, then the descriptions aligned on one edge.
    date_w = max(_text_px(ax, d, renderer, **date_kw) for d, _, _ in events) / px_per_pt
    value_w = max(_text_px(ax, v, renderer, **value_kw) for _, v, _ in events) / px_per_pt
    x_rule = date_w + GAP_PT * 1.5
    x_value = x_rule + GAP_PT * 1.5
    x_desc = x_value + value_w + GAP_PT
    desc_w_px = (w_pt - x_desc) * px_per_pt
    if desc_w_px <= 0:
        raise ValueError("timeline() values are too wide for the figure")

    value_h = t.size.subtitle * 1.35
    desc_h = t.size.body * 1.3
    groups = [(d, [(v, _wrap(ax, s, desc_w_px, renderer, **desc_kw)) for _, v, s in rows])
              for d, rows in groupby(events, key=lambda e: e[0])]

    def row_h(lines):
        return max(value_h, value_h - desc_h + desc_h * len(lines))

    content = TOP_PAD_PT + sum(row_h(lines) for _, rows in groups for _, lines in rows)
    gaps = max(len(groups) - 1, 0)
    min_gap = GROUP_GAP * value_h
    if content + gaps * min_gap > h_pt + 1e-6:
        warnings.warn(
            "hegevis: timeline() content is taller than the plot - make the "
            "figure taller or the descriptions shorter.", stacklevel=2,
        )
    # Spare height goes between the dates, so the timeline fills its box --
    # but never more than double the minimum, or the milestones drift apart.
    gap = min(max(min_gap, (h_pt - content) / gaps), min_gap * 2) if gaps else 0.0

    def ax_xy(x_pt, y_pt):
        return x_pt / w_pt, 1 - y_pt / h_pt

    accent = color or pal.slot(0)
    dots = []
    y = TOP_PAD_PT
    for date, rows in groups:
        for i, (value, lines) in enumerate(rows):
            # Value and first description line share one baseline.
            baseline = y + t.size.subtitle
            if i == 0:
                ax.text(*ax_xy(date_w, baseline), date, ha="right", va="baseline",
                        color=t.ink, transform=ax.transAxes, **date_kw)
                dots.append(baseline - t.size.subtitle * 0.32)
            ax.text(*ax_xy(x_value, baseline), value, ha="left", va="baseline",
                    color=t.ink, transform=ax.transAxes, **value_kw)
            for j, line in enumerate(lines):
                ax.text(*ax_xy(x_desc, baseline + j * desc_h), line, ha="left",
                        va="baseline", color=t.ink_soft, transform=ax.transAxes,
                        **desc_kw)
            y += row_h(lines)
        y += gap

    x_axes = x_rule / w_pt
    ys = [ax_xy(0, d)[1] for d in dots]
    ax.plot([x_axes, x_axes], [ys[0], ys[-1]], color=t.neutral, alpha=0.6,
            linewidth=LINE_PT * 0.6, transform=ax.transAxes, clip_on=False,
            solid_capstyle="butt", zorder=2)
    ax.plot([x_axes] * len(ys), ys, linestyle="none", marker="o",
            markersize=DOT_PT, markeredgewidth=0, color=accent,
            transform=ax.transAxes, clip_on=False, zorder=3)

    ax.set_axis_off()
    return ax
