"""The bar family.

Thin marks with air around them, values at the tip, and a surface gap doing the
separating rather than a stroke around every fill. Bars are capped in absolute
thickness -- letting them fill their slot is what makes a chart read loud.
"""

from __future__ import annotations

import numpy as np

from ..palette import Palette, default_palette
from ..theme import MM, get_theme
from ._data import as_series

MAX_BAR_MM = 6.5      # absolute cap on bar thickness in print (~24px on screen)
SLOT_FILL = 0.62      # of the band, so the leftover is air
GAP_PT = 1.0          # the surface gap between touching fills
LABEL_PAD_PT = 3.0


def _axis_extent_mm(ax, axis: str) -> float:
    fig = ax.figure
    w_in, h_in = fig.get_size_inches()
    box = ax.get_position()
    return (box.width * w_in if axis == "x" else box.height * h_in) / MM


def _thickness(ax, n_slots: int, axis: str, max_mm=MAX_BAR_MM) -> float:
    """Bar thickness in data units (slots are 1 unit), capped in millimetres."""
    extent_mm = _axis_extent_mm(ax, axis)
    slot_mm = extent_mm / max(n_slots, 1)
    return min(SLOT_FILL, max_mm / slot_mm) if slot_mm else SLOT_FILL


def _pt_to_data(ax, pts: float, axis: str) -> float:
    """Convert points to data units along one axis, for the surface gap."""
    fig = ax.figure
    w_in, h_in = fig.get_size_inches()
    box = ax.get_position()
    inches = box.width * w_in if axis == "x" else box.height * h_in
    lo, hi = ax.get_xlim() if axis == "x" else ax.get_ylim()
    return abs(hi - lo) * (pts / 72) / inches if inches else 0.0


def _renderer(fig):
    try:
        return fig.canvas.get_renderer()
    except AttributeError:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        return FigureCanvasAgg(fig).get_renderer()


def _reserve_left_for(ax, labels, t, pad_pt=5.0):
    """Widen the left margin to fit the category labels, never crop them."""
    fig = ax.figure
    renderer = _renderer(fig)
    widest = 0.0
    for text in labels:
        probe = ax.text(0, 0, str(text), fontsize=t.size.tick)
        widest = max(widest, probe.get_window_extent(renderer=renderer).width)
        probe.remove()
    # Room for the label itself, the gap to the axis, AND an outer margin, so a
    # long name sits inside the trim rather than against it.
    outer_in = 4.0 / 25.4
    needed_in = outer_in + (widest + pad_pt) / fig.dpi
    m_left_in = t.layout.margin.left / 25.4
    extra = max(0.0, needed_in - m_left_in)
    fig._hegevis_label_left_in = max(getattr(fig, "_hegevis_label_left_in", 0.0), extra)
    from ..layout import _apply_margins
    _apply_margins(fig, t)


def _legend_above(ax, t, ncols=None):
    """Put the legend in its own band above the plot.

    Inside the axes it either sits on the data or gets clipped by the trim;
    above it, the key reads as part of the chart's header. The column count is
    chosen by measuring, so a long series name never runs off the edge.
    """
    fig = ax.figure
    renderer = _renderer(fig)
    handles, labels = ax.get_legend_handles_labels()
    if not labels:
        return None
    avail_px = ax.get_window_extent(renderer=renderer).width

    leg = None
    for cols in range(ncols or len(labels), 0, -1):
        if leg is not None:
            leg.remove()
        leg = ax.legend(handles, labels, loc="lower left",
                        bbox_to_anchor=(0, 1.0), borderaxespad=0,
                        ncols=cols, frameon=False)
        if leg.get_window_extent(renderer=renderer).width <= avail_px or cols == 1:
            break

    h_in = leg.get_window_extent(renderer=renderer).height / fig.dpi
    fig._hegevis_legend_top_in = max(
        getattr(fig, "_hegevis_legend_top_in", 0.0), h_in + 3 / 72
    )
    from ..layout import _apply_margins
    _apply_margins(fig, t)
    return leg


def _fmt(v: float, unit: str = "") -> str:
    # Normalising to percentages leaves values like 55.000000000000007, which
    # would otherwise print as "55.0" beside a neighbouring "17%".
    if abs(v - round(v)) < 1e-9:
        v = float(round(v))
    if v == int(v) and abs(v) < 1e6:
        s = f"{int(v):,}"
    elif abs(v) >= 100:
        s = f"{v:,.0f}"
    elif abs(v) >= 10:
        s = f"{v:,.1f}"
    else:
        s = f"{v:,.2f}".rstrip("0").rstrip(".")
    return f"{s}{unit}"


def _check_lengths(cats, series, fn):
    """A clear message beats matplotlib's broadcast error."""
    bad = {n: len(v) for n, v in series.items() if len(v) != len(cats)}
    if bad:
        raise ValueError(
            f"{fn}(): {len(cats)} categories but series of length {bad}. "
            "Each series needs one value per category - a transposed frame is "
            "the usual cause."
        )


def ranked(ax, labels, values, *, palette=None, color=None, theme=None,
           sort=True, unit="", label_values=True, highlight=None,
           last=("Other",)):
    """Ranked horizontal bars -- the right form for "who is biggest".

    Horizontal because country and bloc names are long: a horizontal bar gives
    the label a full line of its own instead of rotating it.

    One series means ONE colour for every bar. Colouring each bar darker where
    it is bigger double-encodes what the bar length already shows and burns the
    only free channel in the chart.

    ``highlight`` names bars to keep in colour while the rest drop to grey --
    emphasis, for when the story is about one country in a ranking.
    """
    t = theme or get_theme()
    pal = palette or default_palette(t)
    rows = list(zip([str(l) for l in labels], [float(v) for v in values]))
    if sort:
        # Ascending, so the biggest ends up on top. Residual buckets ("Other")
        # are not a rank -- they belong at the foot of the chart whatever their
        # size, or the reader reads them as a country.
        tail = set(last or ())
        rows.sort(key=lambda kv: (kv[0] not in tail, kv[1]))
    names = [r[0] for r in rows]
    vals = np.array([r[1] for r in rows])
    pos = np.arange(len(rows))

    base = color or pal.slot(0)
    if highlight:
        keep = {highlight} if isinstance(highlight, str) else set(highlight)
        colors = [base if n in keep else t.neutral for n in names]
    else:
        colors = [base] * len(names)

    ax.barh(pos, vals, height=_thickness(ax, len(rows), "y"),
            color=colors, linewidth=0, zorder=3)
    ax.set_yticks(pos, names)
    ax.tick_params(axis="y", length=0)
    _reserve_left_for(ax, names, t)
    ax.grid(axis="x", visible=True)
    ax.grid(axis="y", visible=False)
    ax.set_axisbelow(True)

    if label_values:
        _label_bar_tips(ax, pos, vals, t, unit=unit, horizontal=True)
    return ax


def _label_bar_tips(ax, pos, vals, t, *, unit="", horizontal=True):
    """Values at the tip, moved inside only when they genuinely fit."""
    lo, hi = (ax.get_xlim() if horizontal else ax.get_ylim())
    span = hi - lo
    for p, v in zip(pos, vals):
        outside = v >= 0
        offset = LABEL_PAD_PT if outside else -LABEL_PAD_PT
        xy = (v, p) if horizontal else (p, v)
        ax.annotate(
            _fmt(v, unit), xy=xy, xycoords="data",
            xytext=(offset, 0) if horizontal else (0, offset),
            textcoords="offset points",
            ha=("left" if outside else "right") if horizontal else "center",
            va="center" if horizontal else ("bottom" if outside else "top"),
            fontsize=t.size.label, color=t.ink_soft, zorder=4,
            annotation_clip=False,
        )
    # Give the labels room rather than letting them run into the trim.
    if horizontal:
        ax.set_xlim(lo, hi + span * 0.10)


def grouped(ax, data, *, x=None, y=None, categories=None, palette=None,
            theme=None, unit="", label_values=False):
    """Grouped columns -- a handful of series across a few categories.

    Adjacent bars are separated by a surface gap, never by a stroke.
    """
    t = theme or get_theme()
    pal = palette or default_palette(t)
    xs, series = as_series(data, x=x, y=y)
    cats = [str(c) for c in (categories if categories is not None else xs)]
    _check_lengths(cats, series, "grouped")
    names = list(series)
    colors = pal.for_series(names)

    n = len(names)
    pos = np.arange(len(cats))
    group_w = _thickness(ax, len(cats), "x")
    bar_w = group_w / n
    gap = min(_pt_to_data(ax, GAP_PT, "x"), bar_w * 0.25)

    for i, name in enumerate(names):
        offset = (i - (n - 1) / 2) * bar_w
        ax.bar(pos + offset, series[name], width=bar_w - gap,
               color=colors[name], linewidth=0, zorder=3, label=name)

    ax.set_xticks(pos, cats)
    ax.grid(axis="y", visible=True)
    ax.grid(axis="x", visible=False)
    ax.set_axisbelow(True)
    if n >= 2:
        _legend_above(ax, t)
    return ax


def stacked(ax, data, *, x=None, y=None, categories=None, palette=None,
            theme=None, horizontal=False, label_values=False, unit=""):
    """Stacked bars -- part-to-whole where the total also matters.

    Segments are separated by a surface gap of one consistent width. Interior
    segment labels are only drawn when the text actually fits with padding;
    otherwise the legend carries it, and nothing is clipped.
    """
    t = theme or get_theme()
    pal = palette or default_palette(t)
    xs, series = as_series(data, x=x, y=y)
    cats = [str(c) for c in (categories if categories is not None else xs)]
    _check_lengths(cats, series, "stacked")
    names = list(series)
    colors = pal.for_series(names)
    pos = np.arange(len(cats))

    axis = "y" if horizontal else "x"
    thickness = _thickness(ax, len(cats), axis)
    gap = _pt_to_data(ax, GAP_PT, "x" if horizontal else "y")

    bottoms = np.zeros(len(cats))
    pending = []
    for name in names:
        vals = np.asarray(series[name], dtype=float)
        drawn = np.maximum(vals - gap, 0.0)  # the gap comes out of the segment
        if horizontal:
            ax.barh(pos, drawn, left=bottoms, height=thickness,
                    color=colors[name], linewidth=0, zorder=3, label=name)
        else:
            ax.bar(pos, drawn, bottom=bottoms, width=thickness,
                   color=colors[name], linewidth=0, zorder=3, label=name)
        pending.append((bottoms.copy(), vals, drawn, colors[name]))
        bottoms = bottoms + vals

    if horizontal:
        ax.set_yticks(pos, cats)
        _reserve_left_for(ax, cats, t)
        ax.grid(axis="x", visible=True)
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", length=0)
    else:
        ax.set_xticks(pos, cats)
        ax.grid(axis="y", visible=True)
        ax.grid(axis="x", visible=False)
    ax.set_axisbelow(True)
    if len(names) >= 2:
        _legend_above(ax, t)

    # Labels last: the fit test compares rendered text against rendered segment,
    # so it is only meaningful once the axes has its final limits.
    if label_values:
        ax.autoscale_view()
        for b, vals, drawn, fill in pending:
            _label_segments(ax, pos, b, vals, drawn, fill, t,
                            horizontal=horizontal, unit=unit)
    return ax


def _label_segments(ax, pos, bottoms, vals, drawn, fill, t, *, horizontal, unit):
    """Only label a segment when the text fits inside it with padding."""
    from ..palette import Palette as _P
    ink = _P(t).label_ink(fill)
    fig = ax.figure
    try:
        renderer = fig.canvas.get_renderer()
    except AttributeError:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        renderer = FigureCanvasAgg(fig).get_renderer()

    for p, b, v, d in zip(pos, bottoms, vals, drawn):
        if not np.isfinite(v) or d <= 0:
            continue
        text = _fmt(v, unit)
        probe = ax.text(0, 0, text, fontsize=t.size.label)
        ext = probe.get_window_extent(renderer=renderer)
        probe.remove()
        need_px = (ext.width if horizontal else ext.height) + 6  # padding both sides
        a = ax.transData.transform((b, p) if horizontal else (p, b))
        z = ax.transData.transform((b + d, p) if horizontal else (p, b + d))
        have_px = abs((z[0] - a[0]) if horizontal else (z[1] - a[1]))
        if have_px < need_px:
            continue  # legend + table carry it; never clip, never overflow
        centre = (b + d / 2, p) if horizontal else (p, b + d / 2)
        ax.annotate(text, xy=centre, xycoords="data", ha="center", va="center",
                    fontsize=t.size.label, color=ink, zorder=4)


def share(ax, data, *, x=None, y=None, categories=None, palette=None,
          theme=None, horizontal=True, label_values=True):
    """100% stacked bars -- composition, where only the split matters.

    Normalises each category to 100 and labels the axis in per cent.
    """
    t = theme or get_theme()
    xs, series = as_series(data, x=x, y=y)
    stack = np.vstack([np.asarray(v, dtype=float) for v in series.values()])
    totals = stack.sum(axis=0)
    if np.any(totals <= 0):
        raise ValueError("share() needs a positive total in every category")
    normed = {name: (np.asarray(v, dtype=float) / totals) * 100
              for name, v in series.items()}

    stacked(ax, normed, x=xs, categories=categories, palette=palette, theme=t,
            horizontal=horizontal, label_values=label_values, unit="%")
    if horizontal:
        ax.set_xlim(0, 100)
        ax.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
    else:
        ax.set_ylim(0, 100)
        ax.set_yticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
    return ax
