"""Time series -- the geoeconomics workhorse.

Includes the two things that make a multi-line chart readable in a narrow
print column: direct end labels with real collision handling, and indexing to a
common base so two quantities of different magnitude can share one axis
(the sanctioned alternative to a second y-axis, which this package will not do).
"""

from __future__ import annotations

import warnings

import numpy as np

from ..palette import Palette, default_palette
from ..rc import LINE_PT, SURFACE_GAP_PT
from ..theme import get_theme
from ._data import as_series, last_valid

AREA_ALPHA = 0.10  # a wash, never a saturated block


def index_to(data, base=100.0, at=0, x=None, y=None):
    """Rebase every series so they start at ``base``.

    Two series of different magnitude belong on ONE axis, indexed to a common
    base -- never on two y-scales, whose alignment is arbitrary and invents a
    correlation that is not in the data.

    ``at`` is the positional index of the base period.
    """
    xs, series = as_series(data, x=x, y=y)
    out = {}
    for name, vals in series.items():
        anchor = vals[at]
        if not np.isfinite(anchor) or anchor == 0:
            raise ValueError(f"series {name!r} has no usable base value at position {at}")
        out[name] = vals / anchor * base
    return xs, out


def line(ax, data, *, x=None, y=None, palette=None, emphasis=None,
         label_ends=None, legend="auto", theme=None, **kwargs):
    """Multi-line time series.

    Parameters
    ----------
    emphasis : str | list[str], optional
        Name(s) to keep in colour while everything else drops to the
        de-emphasis grey. When the story is "this one moved", this is the right
        form -- not eight categorical hues.
    label_ends : bool, optional
        Direct-label each line at its right end. Defaults to True for four or
        more series, where colour alone stops being comfortable.
    legend : "auto" | bool
        "auto" shows a legend for two or more series *unless* every line is
        directly labelled, in which case the labels already carry identity and
        a legend would spend scarce column width restating it.
    """
    t = theme or get_theme()
    pal = palette or default_palette(t)
    xs, series = as_series(data, x=x, y=y)
    names = list(series)

    colors = pal.emphasis(names, emphasis) if emphasis else pal.for_series(names)
    lead = set([emphasis] if isinstance(emphasis, str) else (emphasis or []))

    if label_ends is None:
        # Direct labels are a stronger identity channel than a legend, and in a
        # print column they cost less width. Default them on for any multi-line
        # chart; the legend then only appears if the caller asks for it.
        label_ends = len(names) >= 2

    for name in names:
        is_context = bool(emphasis) and name not in lead
        ax.plot(
            xs, series[name],
            color=colors[name],
            linewidth=kwargs.pop("linewidth", LINE_PT) if not is_context else LINE_PT * 0.8,
            zorder=2 if is_context else 3,
            label=name,
            solid_capstyle="round",
            **kwargs,
        )

    # Under emphasis every line is still labelled -- the context lines share one
    # grey, so a legend listing them by name would promise a distinction the
    # chart cannot deliver.
    labelled = set(
        add_end_labels(ax, xs, series, colors, only=set(names), lead=lead, theme=t)
    ) if label_ends else set()

    if legend == "auto":
        # Every line directly labelled? The labels already carry identity, and
        # in an 88mm column a legend would spend scarce width restating it.
        show_legend = len(names) >= 2 and labelled != set(names)
    else:
        show_legend = bool(legend)
    if show_legend:
        ax.legend(loc="upper left", ncols=min(len(names), 3))

    _tidy(ax, t)
    return ax


def add_end_labels(ax, xs, series, colors, *, only=None, lead=None, theme=None,
                   pad_pt=4.0):
    """Direct labels at the right end of each line, nudged apart if they collide.

    When lines converge, stacking labels detaches them from their line and
    reads as noise -- so a label that has to move gets a leader line back to
    its own endpoint, and a badly converging set warns that small multiples
    would read better.
    """
    t = theme or get_theme()
    only = set(only) if only is not None else set(series)
    lead = set(lead or ())
    fig = ax.figure

    points = []
    for name, vals in series.items():
        if name not in only:
            continue
        pt = last_valid(np.asarray(xs), np.asarray(vals, dtype=float))
        if pt is not None:
            points.append((name, pt[0], pt[1]))
    if not points:
        return []

    renderer = _get_renderer(fig)

    # Make room on the right for the widest label, in data coordinates.
    widest = 0.0
    for name, *_ in points:
        probe = ax.text(0, 0, name, fontsize=t.size.label)
        widest = max(widest, probe.get_window_extent(renderer=renderer).width)
        probe.remove()
    # Reserve room in the FIGURE margin, not by widening the x-axis: stretching
    # the axis leaves the tick locator free to place a tick out in the empty
    # space, implying data that does not exist.
    needed_in = (widest + pad_pt * 2) / fig.dpi
    fig._hegevis_label_right_in = max(
        getattr(fig, "_hegevis_label_right_in", 0.0), needed_in
    )
    from ..layout import _apply_margins
    _apply_margins(fig, t)

    # Resolve vertical collisions in display space, then convert the shift back
    # to points so the label can be offset from its own endpoint.
    line_h = t.size.label * 1.25 * fig.dpi / 72
    placed = sorted(
        ((name, xv, yv, ax.transData.transform((0, yv))[1]) for name, xv, yv in points),
        key=lambda r: r[3],
    )
    ys = [r[3] for r in placed]
    for i in range(1, len(ys)):
        if ys[i] - ys[i - 1] < line_h:
            ys[i] = ys[i - 1] + line_h
    drift = (ys[-1] - placed[-1][3]) / 2  # re-centre so the block does not ride up
    ys = [v - drift for v in ys]

    moved = 0
    for (name, xv, yv, orig_py), new_py in zip(placed, ys):
        dy_pt = (new_py - orig_py) * 72 / fig.dpi
        leader = abs(dy_pt) >= 1.0
        moved += leader
        ax.annotate(
            name, xy=(xv, yv), xycoords="data",
            xytext=(pad_pt, dy_pt), textcoords="offset points",
            va="center", ha="left", fontsize=t.size.label,
            color=(t.ink if name in lead else t.ink_muted) if lead else t.ink_soft,
            fontweight=t.weight_medium if name in lead else t.weight_normal,
            annotation_clip=False, zorder=4,
            arrowprops=dict(arrowstyle="-", color=t.axis, linewidth=0.4,
                            shrinkA=0, shrinkB=1) if leader else None,
        )

    if moved > 4:
        warnings.warn(
            f"{moved} end labels had to be displaced - the lines converge at the right "
            "edge. Small multiples usually read better past ~4 converging series.",
            stacklevel=2,
        )
    return [name for name, *_ in placed]


def _get_renderer(fig):
    try:
        return fig.canvas.get_renderer()
    except AttributeError:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        return FigureCanvasAgg(fig).get_renderer()


def area(ax, data, *, x=None, y=None, palette=None, color=None, theme=None):
    """Single-series area: a 10% wash under a full-weight line.

    Area is for ONE series. Several stacked translucent areas stop being
    readable where they overlap -- use :func:`line` instead.
    """
    t = theme or get_theme()
    pal = palette or default_palette(t)
    xs, series = as_series(data, x=x, y=y)
    if len(series) != 1:
        raise ValueError(
            f"area() takes a single series, got {len(series)}. Use line() for several."
        )
    name, vals = next(iter(series.items()))
    c = color or pal.slot(0)
    ax.fill_between(xs, vals, color=c, alpha=AREA_ALPHA, linewidth=0, zorder=2)
    ax.plot(xs, vals, color=c, linewidth=LINE_PT, zorder=3, label=name,
            solid_capstyle="round")
    _tidy(ax, t)
    return ax


def shade_period(ax, start, end, *, label=None, theme=None, color=None):
    """Shade an episode -- a sanctions regime, a crisis window, a tariff round.

    Sits behind the data in a barely-there wash: context should never compete
    with the series it is context for.
    """
    t = theme or get_theme()
    band = ax.axvspan(start, end, color=color or t.grid, alpha=0.55,
                      linewidth=0, zorder=0)
    if label:
        ax.annotate(
            label, xy=(start, 1.0), xycoords=("data", "axes fraction"),
            xytext=(2, -3), textcoords="offset points",
            fontsize=t.size.source, color=t.ink_muted, va="top", ha="left", zorder=1,
        )
    return band


def _tidy(ax, t):
    ax.set_axisbelow(True)
    ax.spines["bottom"].set_color(t.axis)
    ax.tick_params(axis="y", length=0)
