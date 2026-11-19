"""The bar family: ordered rows, ordered columns, and a histogram.

Three forms, and no more. Grouped, stacked and 100%-stacked bars were removed
deliberately: each of them asks a reader to compare lengths that do not share a
baseline, which is the one comparison bars are actually good at. A chart that
needed a stack is nearly always two charts, or a ranked chart of the thing that
matters.

Thin marks with air around them, values at the tip, and a surface gap doing the
separating rather than a stroke around every fill. Bars are capped in absolute
thickness -- letting them fill their slot is what makes a chart read loud.
"""

from __future__ import annotations

import numpy as np

from ..palette import default_palette
from ..theme import MM, get_theme

MAX_BAR_MM = 6.5      # absolute cap on bar thickness in print
MAX_SLOT_MM = 14.0    # absolute cap on bar pitch (bar + gap) in print
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


def _cap_slots(ax, n_slots: int, axis: str, max_mm=MAX_SLOT_MM) -> float:
    """Keep a short ranking together instead of spreading it over the box.

    Three bars dealt across a full-height plot sit so far apart they stop
    reading as one comparison. Past the cap, the axis is padded symmetrically
    so the bars cluster mid-plot at a fixed pitch and the box keeps its shape.

    Returns the slot pitch in millimetres, capped or not.
    """
    extent_mm = _axis_extent_mm(ax, axis)
    slot_mm = extent_mm / max(n_slots, 1)
    if slot_mm <= max_mm:
        return slot_mm
    span = extent_mm / max_mm
    mid = (n_slots - 1) / 2
    set_lim = ax.set_ylim if axis == "y" else ax.set_xlim
    set_lim(mid - span / 2, mid + span / 2)
    return max_mm


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
        probe = ax.text(0, 0, str(text), fontsize=t.size.body)
        widest = max(widest, probe.get_window_extent(renderer=renderer).width)
        probe.remove()
    # Room for the label itself, the gap to the axis, AND an outer margin, so a
    # long name sits inside the box rather than against its edge.
    outer_in = 4.0 / 25.4
    needed_in = outer_in + (widest + pad_pt) / fig.dpi
    m_left_in = t.layout.margin.left / 25.4
    extra = max(0.0, needed_in - m_left_in)
    fig._hegevis_label_left_in = max(getattr(fig, "_hegevis_label_left_in", 0.0), extra)
    from ..layout import _apply_margins
    _apply_margins(fig, t)


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


def _order(labels, values, sort: bool, last, descending: bool):
    """Rows in the order they will be drawn.

    Residual buckets ("Other") are not a rank -- they belong at the end of the
    chart whatever their size, or the reader reads them as a category.
    """
    rows = list(zip([str(l) for l in labels], [float(v) for v in values]))
    if sort:
        tail = set(last or ())
        rows.sort(key=lambda kv: (kv[0] not in tail, kv[1]), reverse=descending)
        if descending:
            # reverse=True also pulled the tail bucket to the front; put it back.
            keep = [r for r in rows if r[0] not in tail]
            rows = keep + [r for r in rows if r[0] in tail]
    return rows


def _bar_colors(names, base, highlight, t):
    """One colour for every bar, unless the caller named one to stand out.

    One series means ONE colour. Colouring each bar darker where it is bigger
    double-encodes what the bar length already shows and burns the only free
    channel in the chart.
    """
    if not highlight:
        return [base] * len(names)
    keep = {highlight} if isinstance(highlight, str) else set(highlight)
    return [base if n in keep else t.neutral for n in names]


def ranked(ax, labels, values, *, palette=None, color=None, theme=None,
           sort=True, unit="", label_values=True, highlight=None,
           last=("Other",), tip_labels=None):
    """Ranked horizontal bars -- the right form for "who is biggest".

    Horizontal because country and bloc names are long: a horizontal bar gives
    the label a full line of its own instead of rotating it.

    ``highlight`` names bars to keep in colour while the rest drop to grey --
    emphasis, for when the story is about one country in a ranking.

    ``tip_labels`` replaces the printed value at each bar's tip, one string per
    label in the order given -- for values the source only states loosely
    ("~75%", "Almost two-thirds"), where printing the plotted number would
    claim a precision the data does not have.
    """
    t = theme or get_theme()
    pal = palette or default_palette(t)
    rows = _order(labels, values, sort, last, descending=False)
    names = [r[0] for r in rows]
    vals = np.array([r[1] for r in rows])
    pos = np.arange(len(rows))

    colors = _bar_colors(names, color or pal.slot(0), highlight, t)
    slot_mm = _cap_slots(ax, len(rows), "y")
    ax.barh(pos, vals, height=min(SLOT_FILL, MAX_BAR_MM / slot_mm),
            color=colors, linewidth=0, zorder=3)

    ax.set_yticks(pos, names)
    # The category axis is labelled on the LEFT even though the house default
    # puts the value scale on the right: these are names, not a scale, and they
    # read as the row's own label only when they sit beside the bar's origin.
    ax.tick_params(axis="y", length=0, labelleft=True, labelright=False)
    _reserve_left_for(ax, names, t)
    ax.grid(axis="x", visible=True)
    ax.grid(axis="y", visible=False)
    ax.set_axisbelow(True)

    if label_values:
        _label_bar_tips(ax, pos, vals, t, unit=unit, horizontal=True,
                        texts=_tip_texts(labels, tip_labels, names))
    return ax


def columns(ax, labels, values, *, palette=None, color=None, theme=None,
            sort=True, unit="", label_values=True, highlight=None,
            last=("Other",), tip_labels=None):
    """Ordered vertical bars -- a ranking where the labels are short.

    The same form as :func:`ranked`, turned on its side. Use it when the
    categories are years, quarters or short codes ("USD", "EUR"); use ``ranked``
    the moment the labels are country or institution names, because rotated
    labels are harder to read than a chart turned ninety degrees.

    Ordered biggest-first, left to right, since that is the direction a reader
    scans.
    """
    t = theme or get_theme()
    pal = palette or default_palette(t)
    rows = _order(labels, values, sort, last, descending=True)
    names = [r[0] for r in rows]
    vals = np.array([r[1] for r in rows])
    pos = np.arange(len(rows))

    colors = _bar_colors(names, color or pal.slot(0), highlight, t)
    ax.bar(pos, vals, width=_thickness(ax, len(rows), "x"),
           color=colors, linewidth=0, zorder=3)

    ax.set_xticks(pos, names)
    ax.grid(axis="y", visible=True)
    ax.grid(axis="x", visible=False)
    ax.set_axisbelow(True)

    if label_values:
        _label_bar_tips(ax, pos, vals, t, unit=unit, horizontal=False,
                        texts=_tip_texts(labels, tip_labels, names))
    return ax


def histogram(ax, values, *, bins="auto", limits=None, palette=None, color=None,
              theme=None):
    """The distribution of one variable.

    Bins are chosen by numpy's ``auto`` rule rather than a round number pulled
    out of the air: a histogram's bin width IS an analytical claim, and 10 bins
    because 10 is a nice number is the commonest way to make a distribution say
    something it does not.

    Unlike the ranked forms this one is NOT sorted -- the x-axis is a real
    number line, and reordering it would destroy the shape that is the point.
    """
    t = theme or get_theme()
    pal = palette or default_palette(t)
    vals = np.asarray([v for v in np.asarray(values, dtype=float)
                       if np.isfinite(v)])
    if not len(vals):
        raise ValueError("histogram() needs at least one finite value")

    counts, edges = np.histogram(vals, bins=bins, range=limits)
    widths = np.diff(edges)
    # The surface gap comes out of the bar, so neighbouring bins are separated
    # by the ground rather than by a stroke -- the same rule as every other fill
    # in the house style.
    gap = widths * 0.06

    ax.bar(edges[:-1] + widths / 2, counts, width=widths - gap,
           color=color or pal.slot(0), linewidth=0, zorder=3, align="center")

    ax.grid(axis="y", visible=True)
    ax.grid(axis="x", visible=False)
    ax.set_axisbelow(True)
    ax.set_ylim(bottom=0)
    return ax


def _tip_texts(labels, tip_labels, names):
    """Caller's tip labels, re-ordered to follow the bars after sorting."""
    if tip_labels is None:
        return None
    labels, tip_labels = [str(l) for l in labels], list(tip_labels)
    if len(tip_labels) != len(labels):
        raise ValueError("tip_labels needs one entry per bar")
    by_name = dict(zip(labels, tip_labels))
    return [by_name[n] for n in names]


def _label_bar_tips(ax, pos, vals, t, *, unit="", horizontal=True, texts=None):
    """Values at the tip, outside the bar, never clipped by the axis."""
    lo, hi = (ax.get_xlim() if horizontal else ax.get_ylim())
    span = hi - lo
    texts = texts or [_fmt(v, unit) for v in vals]
    for p, v, text in zip(pos, vals, texts):
        outside = v >= 0
        offset = LABEL_PAD_PT if outside else -LABEL_PAD_PT
        xy = (v, p) if horizontal else (p, v)
        ax.annotate(
            text, xy=xy, xycoords="data",
            xytext=(offset, 0) if horizontal else (0, offset),
            textcoords="offset points",
            ha=("left" if outside else "right") if horizontal else "center",
            va="center" if horizontal else ("bottom" if outside else "top"),
            fontsize=t.size.body, color=t.ink_soft, zorder=4,
            annotation_clip=False,
        )
    # Give the labels room rather than letting them run into the box edge.
    if horizontal:
        ax.set_xlim(lo, hi + span * 0.10)
    else:
        ax.set_ylim(lo, hi + span * 0.10)
