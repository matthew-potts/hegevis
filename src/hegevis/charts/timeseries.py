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

    # Tidy first: the end labels measure the y tick labels to place themselves
    # clear of the right-hand scale, so the ticks have to be final before they
    # are measured, not after.
    _tidy(ax, t)

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
        probe = ax.text(0, 0, name, fontsize=t.size.body)
        widest = max(widest, probe.get_window_extent(renderer=renderer).width)
        probe.remove()
    # The value scale lives on the right in this house style, so the end labels
    # have to clear it -- otherwise the series name lands on top of its own
    # axis numbers. Reserve for both, and push the labels out past the ticks.
    scale_px = _ytick_label_width(ax, renderer, t)
    scale_pt = scale_px * 72 / fig.dpi
    # Reserve room in the FIGURE margin, not by widening the x-axis: stretching
    # the axis leaves the tick locator free to place a tick out in the empty
    # space, implying data that does not exist.
    needed_in = (widest + scale_px + pad_pt * 3) / fig.dpi
    fig._hegevis_label_right_in = max(
        getattr(fig, "_hegevis_label_right_in", 0.0), needed_in
    )
    from ..layout import _apply_margins
    _apply_margins(fig, t)
    # Past the scale, plus a clear gap: a series name touching its own axis
    # numbers reads as one run-on string ("102European Union").
    x_offset_pt = pad_pt + scale_pt + pad_pt * 2

    # Resolve vertical collisions in display space, then convert the shift back
    # to points so the label can be offset from its own endpoint.
    line_h = t.size.body * 1.25 * fig.dpi / 72
    placed = sorted(
        ((name, xv, yv, ax.transData.transform((0, yv))[1]) for name, xv, yv in points),
        key=lambda r: r[3],
    )
    ys = _spread([r[3] for r in placed], line_h)

    moved = 0
    for (name, xv, yv, orig_py), new_py in zip(placed, ys):
        dy_pt = (new_py - orig_py) * 72 / fig.dpi
        leader = abs(dy_pt) >= 1.0
        moved += leader
        ax.annotate(
            name, xy=(xv, yv), xycoords="data",
            xytext=(x_offset_pt, dy_pt), textcoords="offset points",
            va="center", ha="left", fontsize=t.size.body,
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


def _spread(ys, min_gap):
    """Push a sorted stack of label positions apart to clear ``min_gap``.

    Re-centred afterwards, so a crowded block grows symmetrically about where
    it wanted to be instead of riding upward off the top of the chart.
    """
    if not ys:
        return []
    out = list(ys)
    for i in range(1, len(out)):
        if out[i] - out[i - 1] < min_gap:
            out[i] = out[i - 1] + min_gap
    drift = (out[-1] - ys[-1]) / 2
    return [v - drift for v in out]


def _widest_px(ax, texts, size, renderer) -> float:
    widest = 0.0
    for s in texts:
        if not s:
            continue
        probe = ax.text(0, 0, s, fontsize=size)
        widest = max(widest, probe.get_window_extent(renderer=renderer).width)
        probe.remove()
    return widest


def _ytick_label_width(ax, renderer, t) -> float:
    """Width in pixels of the widest y tick label, measured before a draw.

    The labels do not exist as text until the figure is drawn, so the tick
    values are formatted and measured directly rather than read off the axis.
    """
    fmt = ax.yaxis.get_major_formatter()
    locs = list(ax.get_yticks())
    # A ScalarFormatter returns "" until it has been given its locations, which
    # happens at draw time. Priming it here is what makes the measurement real
    # rather than zero -- and a zero here silently drops the end labels on top
    # of the axis numbers.
    try:
        fmt.set_locs(locs)
    except Exception:
        pass
    widest = 0.0
    for loc in locs:
        try:
            text = fmt(loc)
        except Exception:
            text = ""
        if not text:
            text = f"{loc:g}"
        probe = ax.text(0, 0, text, fontsize=t.size.body)
        widest = max(widest, probe.get_window_extent(renderer=renderer).width)
        probe.remove()
    return widest


def slope(ax, data, *, labels=None, palette=None, emphasis=None, theme=None,
          unit="", label_values=True, value_labels=None, value_axis=False,
          name_side="start"):
    """A slope chart: two points in time, one line each, ranked at both ends.

    The right form for "who moved, and in which direction" across exactly two
    periods. A full time series would spend an entire chart's width showing
    fourteen points nobody reads, when the story is the first and the last.

    ``data`` maps each name to its ``(start, end)`` pair. ``labels`` names the
    two periods for the axis; it defaults to "Before" and "After".

    ``value_labels`` maps a name to the ``(start, end)`` text printed in place
    of its values -- for a source that gives a range ("0.20-0.25%") where the
    line has to be drawn at a single point, or to carry the size of the move.
    Names left out keep their formatted values.

    ``value_axis`` adds a value scale and gridlines on the left, for when the
    levels matter as well as the change. The start labels then move inside the
    plot, between the scale and the lines, so the two never collide.

    ``name_side`` puts the series names at the "start" (default) or "end" of
    the lines -- the end reads better when the story is where things finished.
    """
    t = theme or get_theme()
    pal = palette or default_palette(t)
    pairs = {str(k): (float(v[0]), float(v[1])) for k, v in dict(data).items()}
    if not pairs:
        raise ValueError("slope() needs at least one series")
    bad = [k for k, v in dict(data).items() if len(v) != 2]
    if bad:
        raise ValueError(
            f"slope() takes exactly two values per series - {bad} had a different "
            "length. For more than two periods use line()."
        )

    if name_side not in ("start", "end"):
        raise ValueError(f'name_side must be "start" or "end", not {name_side!r}')
    names = list(pairs)
    colors = pal.emphasis(names, emphasis) if emphasis else pal.for_series(names)
    lead = set([emphasis] if isinstance(emphasis, str) else (emphasis or []))

    for name in names:
        y0, y1 = pairs[name]
        is_context = bool(emphasis) and name not in lead
        ax.plot([0, 1], [y0, y1], color=colors[name],
                linewidth=LINE_PT if not is_context else LINE_PT * 0.8,
                zorder=2 if is_context else 3, label=name,
                marker="o", markersize=3.0, markeredgewidth=0,
                solid_capstyle="round")

    ax.set_xlim(-0.04, 1.04)
    if value_labels:
        unknown = set(map(str, value_labels)) - set(names)
        if unknown:
            raise ValueError(f"value_labels names series not in data: {sorted(unknown)}")
        bad = [k for k, v in value_labels.items() if len(v) != 2]
        if bad:
            raise ValueError(f"value_labels needs a (start, end) pair - {bad} did not")
    _label_slope_ends(ax, pairs, colors, lead, t, unit=unit,
                      label_values=label_values,
                      value_labels={str(k): v for k, v in (value_labels or {}).items()},
                      inside_start=value_axis, name_side=name_side)
    ax.set_xticks([0, 1], list(labels) if labels else ["Before", "After"])
    if value_axis:
        from matplotlib.ticker import FuncFormatter
        ax.grid(axis="y", visible=True)
        ax.grid(axis="x", visible=False)
        ax.tick_params(axis="y", length=0, labelleft=True, labelright=False)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _fmt_value(v, unit)))
    else:
        # No value scale and no gridlines by default: the lines ARE the
        # comparison, and a slope chart with a y-axis invites a reader to
        # measure levels off a form built to show change.
        ax.grid(False)
        ax.tick_params(axis="y", length=0, labelleft=False, labelright=False)
    for side in ("left", "right", "top"):
        ax.spines[side].set_visible(False)
    ax.set_axisbelow(True)
    return ax


def _fmt_value(v: float, unit: str = "") -> str:
    from .bars import _fmt
    return _fmt(v, unit)


def _label_slope_ends(ax, pairs, colors, lead, t, *, unit, label_values,
                      value_labels=None, inside_start=False, name_side="start",
                      pad_pt=5.0):
    """Name and value at the left end, value at the right, nothing clipped.

    Both ends are labelled because the whole point of the form is that a reader
    can take the ranking at the start, the ranking at the end, and the crossings
    between them without consulting a legend. That only works if the labels are
    inside the box and not on top of each other, so the figure margins are
    widened to fit them and any stack that collides is spread apart.
    """
    fig = ax.figure
    renderer = _get_renderer(fig)
    names = list(pairs)

    value_labels = value_labels or {}

    def value_text(n, i):
        if n in value_labels:
            return str(value_labels[n][i])
        return _fmt_value(pairs[n][i], unit)

    if name_side == "end":
        left_text = {n: (value_text(n, 0) if label_values else "") for n in names}
        right_text = {n: (f"{n}  {value_text(n, 1)}" if label_values else n)
                      for n in names}
    else:
        # Inside the plot, width is taken from the lines themselves, so the
        # name stacks over its value rather than running beside it.
        sep = "\n" if inside_start else "  "
        left_text = {n: (f"{n}{sep}{value_text(n, 0)}" if label_values else n)
                     for n in names}
        right_text = {n: (value_text(n, 1) if label_values else "")
                      for n in names}
    # Nothing to fit at the start means nothing to move inside the plot.
    inside_start = inside_start and any(left_text.values())

    # Reserve room in the FIGURE margins for both label columns before placing
    # anything: the labels sit outside the axes, so widening the axes would not
    # help and stretching the x-range would invent space between the periods.
    from ..layout import _apply_margins
    # Plus an outer margin, as ranked() keeps, so the longest name sits inside
    # the figure rather than against its edge.
    outer_in = 4.0 / 25.4
    left_in = outer_in + (_widest_px(ax, left_text.values(), t.size.body, renderer)
                          + pad_pt * 2) / fig.dpi
    right_in = outer_in + (_widest_px(ax, right_text.values(), t.size.body, renderer)
                           + pad_pt) / fig.dpi
    if not inside_start:
        fig._hegevis_label_left_in = max(
            getattr(fig, "_hegevis_label_left_in", 0.0),
            max(0.0, left_in - t.layout.margin.left / 25.4),
        )
    # As on the left, the theme margin counts towards the room the labels need
    # rather than being added on top of it.
    fig._hegevis_label_right_in = max(
        getattr(fig, "_hegevis_label_right_in", 0.0),
        max(0.0, right_in - t.layout.margin.right / 25.4),
    )
    _apply_margins(fig, t)

    if inside_start:
        # The left margin belongs to the value scale, so the start labels go
        # inside the plot: open the x-range to the left by exactly their width,
        # leaving the distance between the two periods untouched.
        width_px = ax.get_window_extent(renderer=renderer).width
        # One more pad than the labels need, to clear the scale's tick labels.
        k = (left_in - outer_in + pad_pt / 72) * fig.dpi / width_px
        hi = ax.get_xlim()[1]
        ax.set_xlim(-hi * k / (1 - k), hi)
    # Gridlines would otherwise run through labels sitting inside the plot.
    mask = (dict(boxstyle="square,pad=0.1", facecolor=t.surface, edgecolor="none")
            if inside_start else None)

    line_h = t.size.body * 1.25 * fig.dpi / 72
    stacked = inside_start and label_values and name_side == "start"
    lines_per = {"start": 2 if stacked else 1, "end": 1}
    for side, x, texts, ha, sign in (
        ("start", 0.0, left_text, "right", -1),
        ("end", 1.0, right_text, "left", 1),
    ):
        rows = sorted(
            ((n, pairs[n][0 if side == "start" else 1]) for n in names),
            key=lambda r: r[1],
        )
        orig = [ax.transData.transform((0, v))[1] for _, v in rows]
        spread = _spread(orig, line_h * lines_per[side])
        for (name, value), py, new_py in zip(rows, orig, spread):
            if not texts[name]:
                continue
            is_context = bool(lead) and name not in lead
            ax.annotate(
                texts[name], xy=(x, value), xycoords="data",
                xytext=(sign * pad_pt, (new_py - py) * 72 / fig.dpi),
                textcoords="offset points", ha=ha, va="center",
                fontsize=t.size.body, bbox=mask,
                color=t.ink_muted if is_context else t.ink_soft,
                fontweight=t.weight_medium if name in lead else t.weight_normal,
                annotation_clip=False, zorder=4,
            )


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
            fontsize=t.size.body, color=t.ink_muted, va="top", ha="left", zorder=1,
        )
    return band


MAX_X_TICKS = 6   # in an 88mm portrait box, more than this collides
MAX_Y_TICKS = 6


def _tidy(ax, t):
    ax.set_axisbelow(True)
    ax.spines["bottom"].set_color(t.axis)
    # The value scale sits on the right, so the ticks carry no marks -- the
    # gridlines already show where the levels are.
    ax.tick_params(axis="y", length=0, labelleft=False, labelright=True)
    _thin_ticks(ax)


def _thin_ticks(ax):
    """Cap the tick count so labels never collide in a narrow portrait box.

    matplotlib's defaults are chosen for a wide figure on screen. At 88mm with
    four-digit years, its idea of a reasonable number of ticks runs the labels
    into each other -- a chart is easier to read with six dates on it than with
    fifteen overlapping ones.
    """
    import matplotlib.dates as mdates
    from matplotlib.ticker import MaxNLocator

    if isinstance(ax.xaxis.get_major_locator(), mdates.DateLocator):
        loc = mdates.AutoDateLocator(minticks=3, maxticks=MAX_X_TICKS)
        ax.xaxis.set_major_locator(loc)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    else:
        ax.xaxis.set_major_locator(MaxNLocator(nbins=MAX_X_TICKS, prune=None))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=MAX_Y_TICKS))
