"""Figures at true printed size, and the furniture around them.

Two things this module exists to guarantee:

1. **A figure is built at the width it will print at.** Ask for ``size="col1"``
   and you get a figure exactly one column wide, so 7.5pt type is 7.5pt on
   paper. Nothing is scaled on the way to the page -- which is also why the
   house style never saves with ``bbox_inches="tight"``.
2. **Every chart carries the same furniture, in the same place.** Title,
   subtitle, source, note and the masthead mark are placed by the package, not
   by each analyst, so they line up across articles.
"""

from __future__ import annotations

import warnings

import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import Rectangle

from .rc import is_active, use
from .theme import MM, Theme, get_theme

PT = 1 / 72  # points -> inches
LINE_SPACING = 1.25
BLOCK_GAP_PT = 3.0  # between title and subtitle, and above the source line
TAB_GAP_MM = 3.0    # between the masthead tab and the first line of the title


def _renderer(fig):
    """A renderer for text measurement, whatever backend is active."""
    try:
        return fig.canvas.get_renderer()
    except AttributeError:
        return FigureCanvasAgg(fig).get_renderer()


def _text_width_in(fig, s: str, size: float, weight, family=None) -> float:
    kw = {"fontfamily": list(family)} if family else {}
    t = fig.text(0, 0, s, fontsize=size, fontweight=weight, **kw)
    w = t.get_window_extent(renderer=_renderer(fig)).width / fig.dpi
    t.remove()
    return w


def wrap(fig, s: str, width_in: float, size: float, weight=400,
         family=None) -> list[str]:
    """Word-wrap by measuring the actual face, not by counting characters.

    ``family`` matters: the title is set in the serif and the rest in the sans,
    and the two measure differently at the same point size. Wrapping the title
    against the sans would put the break in the wrong place.
    """
    if not s:
        return []
    words, lines, cur = s.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if cur and _text_width_in(fig, trial, size, weight, family) > width_in:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def figure(size="col1", *, height=None, ratio=None, theme: Theme | None = None,
           nrows=1, ncols=1, sharex=False, sharey=False, **kwargs):
    """Create a figure sized to the publication's grid.

    Parameters
    ----------
    size : "col1" | "col15" | "col2" | "page" | float
        A named column width from the theme, or a literal width in millimetres.
    height : float, optional
        Height in millimetres. Defaults to ``width * ratio``.
    ratio : float, optional
        Height-to-width ratio when ``height`` is not given.

    Returns ``(fig, ax)`` for a single panel, or ``(fig, axes)`` for a grid.
    """
    t = theme or get_theme()
    # A figure from this package is in the house style whether or not the script
    # remembered to call use() -- otherwise the helpers and the style can
    # disagree, which is the exact drift the package exists to prevent.
    if not is_active(t):
        use(t)
    w_mm = t.layout.width_mm(size)
    h_mm = height if height is not None else w_mm * (ratio or t.layout.default_ratio)
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(w_mm * MM, h_mm * MM),
        sharex=sharex, sharey=sharey, **kwargs,
    )
    fig.set_facecolor(t.surface)
    for ax in (axes.flat if hasattr(axes, "flat") else [axes]):
        ax.set_facecolor(t.surface)
    # Before the margins, so the plot area is laid out around it rather than
    # having it dropped on top afterwards.
    _tab(fig, t)
    _apply_margins(fig, t)
    return fig, axes


def _tab(fig, t: Theme):
    """The solid rectangle top-left that opens every chart.

    It is the one mark on the page that is the same on every chart in every
    article, which is what makes a reader recognise the chart as ours before
    reading a word of it. Placed in figure coordinates so it never moves with
    the plot area, and drawn in brand orange rather than a borrowed red.
    """
    if getattr(fig, "_hegevis_tab", None) is not None:
        return fig._hegevis_tab
    w_in, h_in = fig.get_size_inches()
    m = t.layout.margin
    rect = Rectangle(
        ((m.left * MM) / w_in, 1 - (t.tab.top_mm + t.tab.height_mm) * MM / h_in),
        (t.tab.width_mm * MM) / w_in, (t.tab.height_mm * MM) / h_in,
        transform=fig.transFigure, facecolor=t.tab.color, edgecolor="none", zorder=5,
    )
    fig.add_artist(rect)
    fig._hegevis_tab = rect
    return rect


def _check_words(kind: str, s: str, limit: int) -> None:
    """Warn when a piece of furniture is running long.

    Not truncated: cutting an analyst's title silently would be worse than
    shipping a long one. The warning puts the decision back with the person who
    can actually make it, before the chart reaches the page.
    """
    n = len(s.split())
    if n > limit:
        warnings.warn(
            f"hegevis: {kind} is {n} words, over the house limit of {limit}. "
            "A chart carries a headline, not a paragraph - cut it, or move the "
            "detail into the body text.",
            stacklevel=3,
        )


def _apply_margins(fig, t: Theme, extra_top_in=0.0, extra_bottom_in=0.0):
    w_in, h_in = fig.get_size_inches()
    m = t.layout.margin
    # Direct end labels live in the right margin rather than inside the data
    # area: widening the x-axis to fit them would imply data that is not there.
    extra_right_in = getattr(fig, "_hegevis_label_right_in", 0.0)
    # Long category names -- "United States", "European Union" -- need more than
    # a fixed left margin, or they are silently cropped.
    extra_left_in = getattr(fig, "_hegevis_label_left_in", 0.0)
    # A legend above the plot needs its own band, or the title lands on it.
    extra_top_in = extra_top_in + getattr(fig, "_hegevis_legend_top_in", 0.0)
    fig.subplots_adjust(
        left=(m.left * MM + extra_left_in) / w_in,
        right=1 - (m.right * MM + extra_right_in) / w_in,
        top=1 - (m.top * MM + extra_top_in) / h_in,
        bottom=(m.bottom * MM + extra_bottom_in) / h_in,
    )


def finish(fig, *, title=None, subtitle=None, source=None, note=None,
           theme: Theme | None = None):
    """Add the house furniture and make room for it.

    Text is measured and wrapped against the real figure width, then the plot
    area is pushed down or up by exactly as much as the text needs -- so a long
    two-line title never collides with the chart, and a short one never leaves
    a gap.

    ``source`` is prefixed "Source: " automatically; pass the bare citation.

    The masthead tab is added here if the figure does not already carry it --
    it is furniture like the source line, not something to opt into.
    """
    t = theme or get_theme()
    _tab(fig, t)
    if title:
        _check_words("title", title, t.text.title_words)
    if subtitle:
        _check_words("subtitle", subtitle, t.text.subtitle_words)
    if source or note:
        _check_words("footnote", " ".join(filter(None, (source, note))),
                     t.text.footnote_words)
    w_in, h_in = fig.get_size_inches()
    m = t.layout.margin
    text_w_in = w_in - (m.left + m.right) * MM
    # The footer now has the full measure to itself: nothing else sits in the
    # bottom band.
    foot_w_in = text_w_in

    # -- top block: title then subtitle -------------------------------------
    # The title takes the display face; everything below it stays in the sans.
    # The house sans is appended as a last resort so an unlicensed machine
    # degrades to the chart face rather than to matplotlib's DejaVu.
    title_family = list(t.titles) + list(t.family)
    title_lines = wrap(fig, title, text_w_in, t.size.title, t.weight_bold,
                       title_family) if title else []
    sub_lines = wrap(fig, subtitle, text_w_in, t.size.subtitle, t.weight_normal) if subtitle else []

    top_in = 0.0
    if title_lines:
        top_in += len(title_lines) * t.size.title * LINE_SPACING * PT
    if sub_lines:
        if title_lines:
            top_in += BLOCK_GAP_PT * PT
        top_in += len(sub_lines) * t.size.subtitle * LINE_SPACING * PT

    # -- bottom block: source, then note ------------------------------------
    foot = []
    if source:
        foot.extend(wrap(fig, f"Source: {source}", foot_w_in, t.size.source))
    if note:
        foot.extend(wrap(fig, note, foot_w_in, t.size.source))
    bottom_in = (len(foot) * t.size.source * LINE_SPACING * PT
                 + (BLOCK_GAP_PT * PT if foot else 0.0))

    # The default top margin already reserves room for a one-line title; only
    # the overflow past it needs to push the plot down.
    reserved_top_in = max(0.0, top_in - (m.top * MM) * 0.55)
    _apply_margins(fig, t, extra_top_in=reserved_top_in, extra_bottom_in=bottom_in)

    left = (m.left * MM) / w_in
    # The title hangs off the bottom of the tab, not off the top of the box:
    # the tab is the fixed thing, so the title lands in the same place on every
    # chart whatever the box height.
    y = 1 - (t.tab.top_mm + t.tab.height_mm + TAB_GAP_MM) * MM / h_in

    for line in title_lines:
        y -= t.size.title * LINE_SPACING * PT / h_in
        fig.text(left, y, line, fontsize=t.size.title, fontweight=t.weight_bold,
                 fontfamily=title_family, color=t.ink, ha="left", va="baseline")
    if sub_lines:
        if title_lines:
            y -= BLOCK_GAP_PT * PT / h_in
        for line in sub_lines:
            y -= t.size.subtitle * LINE_SPACING * PT / h_in
            fig.text(left, y, line, fontsize=t.size.subtitle,
                     fontweight=t.weight_normal, color=t.ink_soft,
                     ha="left", va="baseline")

    if foot:
        y = (2.5 * MM) / h_in + (len(foot) - 1) * t.size.source * LINE_SPACING * PT / h_in
        for line in foot:
            fig.text(left, y, line, fontsize=t.size.source, color=t.ink_muted,
                     ha="left", va="baseline")
            y -= t.size.source * LINE_SPACING * PT / h_in

    return fig
