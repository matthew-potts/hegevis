"""The house look, as matplotlib rcParams.

``hegevis.use()`` restyles *any* matplotlib code -- an analyst who already has
a working script gets the house look by adding one line, without learning a new
API. The chart helpers build on the same rcParams, so the two levels can never
drift apart.

Weights are in POINTS, not pixels. The method's specs (2px lines, hairline
grids) are calibrated for screens at 1x; on paper the equivalent ink is a bit
under half that, and a figure built at true column width prints those points
exactly as set.
"""

from __future__ import annotations

import warnings
from contextlib import contextmanager

import matplotlib as mpl

from . import fonts
from .theme import Theme, get_theme

# Print equivalents of the method's screen specs.
LINE_PT = 1.6        # data lines: the reference charts carry a confident stroke
HAIRLINE_PT = 0.4    # gridlines
BASELINE_PT = 0.8    # the zero/category baseline is real ink, not a hairline
MARKER_PT = 4.0      # marker size ("8px" diameter)
SURFACE_GAP_PT = 1.0  # the surface gap between touching fills

_font_warned = False


def resolve_font(families) -> tuple[str, list[str]]:
    """Return (first available family, the ones that were missing).

    Registers the licensed faces from ``assets/fonts/`` first, so a machine
    with the zip unpacked into the package works the same as one with the
    faces installed system-wide.

    Falls back to matplotlib's bundled DejaVu Sans rather than failing -- a
    missing brand font should not stop an analyst working, but it must not pass
    silently either, or a chart ships in the wrong face.
    """
    fonts.register()
    found, missing = fonts.available(families)
    return (found or "DejaVu Sans"), missing


def rc_params(theme: Theme | None = None) -> dict:
    """The full rcParams dict for a theme. Inspectable, testable, no side effects."""
    global _font_warned
    t = theme or get_theme()
    body, missing = resolve_font(t.family)
    if missing and not _font_warned:
        _font_warned = True
        warnings.warn(
            f"hegevis: font {missing[0]!r} is not installed"
            + (f" (nor {', '.join(repr(m) for m in missing[1:])})" if len(missing) > 1 else "")
            + f"; falling back to {body!r}. Charts will NOT be in the house face. "
            "Drop the licensed faces into src/hegevis/assets/fonts/, install them "
            "system-wide, or edit [type].family in the theme file.",
            stacklevel=3,
        )

    return {
        # -- type ------------------------------------------------------------
        "font.family": "sans-serif",
        "font.sans-serif": [body, *t.family, "DejaVu Sans"],
        "font.size": t.size.body,
        "font.weight": t.weight_normal,

        # -- figure & surface -------------------------------------------------
        "figure.facecolor": t.surface,
        "figure.edgecolor": t.surface,
        "figure.frameon": False,
        "axes.facecolor": t.surface,
        "axes.edgecolor": t.axis,
        "savefig.facecolor": t.surface,
        "savefig.edgecolor": t.surface,
        "savefig.transparent": False,

        # -- vector output, print-ready ---------------------------------------
        # fonttype 42 embeds a TrueType subset in the PDF/PS, so the file opens
        # correctly on a machine without the licensed brand face installed.
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "pdf.compression": 6,
        # 'none' keeps SVG text as real text (editable in Illustrator, needs the
        # font installed). export.save(..., outline_text=True) switches to
        # 'path' when prepress wants outlines instead.
        "svg.fonttype": "none",
        # NOT 'tight': a tight bbox silently changes the figure width, and the
        # whole point of building at true column width is that it lands on the
        # page at exactly that width.
        "savefig.bbox": "standard",
        "savefig.pad_inches": 0.0,
        "savefig.dpi": 600,  # only relevant if someone exports a raster proof

        # -- axes -------------------------------------------------------------
        "axes.titlesize": t.size.title,
        "axes.titleweight": t.weight_bold,
        "axes.titlecolor": t.ink,
        "axes.titlelocation": "left",
        "axes.titlepad": 6.0,
        "axes.labelsize": t.size.body,
        "axes.labelcolor": t.ink_muted,
        "axes.labelweight": t.weight_normal,
        "axes.linewidth": BASELINE_PT,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,   # the gridlines carry the scale
        "axes.spines.bottom": True,  # the baseline is real, so it stays
        "axes.axisbelow": True,      # data over grid, always
        "axes.prop_cycle": mpl.cycler(color=list(t.series)),
        "axes.unicode_minus": True,

        # -- grid: solid hairlines, one step off the surface, recessive -------
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": t.grid,
        "grid.linestyle": "-",   # never dashed: dashing reads as "projection"
        "grid.linewidth": HAIRLINE_PT,
        "grid.alpha": 1.0,

        # -- ticks ------------------------------------------------------------
        # The value scale is labelled on the RIGHT, following the house charts:
        # a reader scanning a line to its latest value finds the number where
        # the line ends, instead of tracking back across the plot.
        "xtick.color": t.axis,
        "xtick.labelcolor": t.ink_muted,
        "xtick.labelsize": t.size.body,
        "xtick.direction": "out",
        "xtick.major.size": 3.0,
        "xtick.major.width": BASELINE_PT,
        "xtick.minor.size": 1.5,
        "xtick.major.pad": 3.0,
        "ytick.color": t.axis,
        "ytick.labelcolor": t.ink_muted,
        "ytick.labelsize": t.size.body,
        "ytick.direction": "out",
        "ytick.major.size": 0.0,   # gridlines already mark the scale
        "ytick.major.width": 0.0,
        "ytick.major.pad": 3.0,
        "ytick.left": False,
        "ytick.right": True,
        "ytick.labelleft": False,
        "ytick.labelright": True,

        # -- marks ------------------------------------------------------------
        "lines.linewidth": LINE_PT,
        "lines.solid_capstyle": "round",
        "lines.solid_joinstyle": "round",
        "lines.markersize": MARKER_PT,
        "lines.markeredgewidth": SURFACE_GAP_PT,  # the surface ring
        "lines.markeredgecolor": t.surface,
        "patch.linewidth": 0.0,
        "patch.edgecolor": t.surface,
        "patch.force_edgecolor": False,
        "hatch.linewidth": 0.4,

        # -- legend: never a box, never a shadow ------------------------------
        "legend.frameon": False,
        "legend.fontsize": t.size.body,
        "legend.labelcolor": t.ink_soft,
        "legend.handlelength": 1.2,
        "legend.handletextpad": 0.5,
        "legend.columnspacing": 1.4,
        "legend.borderpad": 0.0,
        "legend.borderaxespad": 0.0,

        # -- text --------------------------------------------------------------
        "text.color": t.ink,
        "date.autoformatter.year": "%Y",
        "date.autoformatter.month": "%b %Y",
    }


# The rcParams that decide what lands in the FILE rather than how the artists
# look. save() re-applies these itself, so output is correct even if a script
# built its figure before calling use().
OUTPUT_KEYS = (
    "pdf.fonttype", "ps.fonttype", "svg.fonttype", "pdf.compression",
    "savefig.bbox", "savefig.pad_inches", "savefig.facecolor",
    "savefig.edgecolor", "savefig.transparent", "savefig.dpi",
)


def output_params(theme: Theme | None = None) -> dict:
    rc = rc_params(theme)
    return {k: rc[k] for k in OUTPUT_KEYS}


def is_active(theme: Theme | None = None) -> bool:
    """Whether the house style is currently in force."""
    t = theme or get_theme()
    return (mpl.rcParams["axes.prop_cycle"].by_key().get("color") == list(t.series)
            and mpl.rcParams["figure.facecolor"] == t.surface)


def use(theme: Theme | None = None) -> Theme:
    """Apply the house style globally. The one-liner for existing scripts."""
    t = theme or get_theme()
    mpl.rcParams.update(rc_params(t))
    return t


@contextmanager
def style(theme: Theme | None = None):
    """Apply the house style for a block only, restoring rcParams after."""
    t = theme or get_theme()
    with mpl.rc_context(rc_params(t)):
        yield t
