"""Getting a figure onto the page.

Vector by default, at the exact width it was built for, with the type embedded
so the file opens correctly on a machine that does not have the licensed brand
face installed.

On colour: matplotlib emits RGB, and the RGB -> CMYK conversion belongs in
prepress where the press profile lives. Rather than pretend to do colour
management it cannot do, this module writes a *manifest* -- every colour a
figure actually used, with the CMYK build the art desk declared for it in the
theme -- so prepress pins agreed values instead of letting the RIP guess.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib as mpl
from matplotlib.colors import to_hex

from . import logo as _logo
from .color import simulate_hex
from .rc import output_params
from .theme import Theme, get_theme

VECTOR = {".pdf", ".svg", ".eps", ".ps"}


def colors_used(fig) -> set[str]:
    """Every colour actually drawn in the figure, as hex.

    Walks the artists rather than the theme, so it catches a stray colour an
    analyst hard-coded past the palette. The masthead mark is skipped: it is a
    placed raster, and prepress handles its inks from the brand artwork rather
    than from a chart's colour manifest.
    """
    found: set[str] = set()

    def add(c):
        try:
            if c is None:
                return
            h = to_hex(c)
        except (ValueError, TypeError):
            return
        found.add(h.lower())

    for ax in fig.get_axes():
        if _logo.is_logo_axes(ax):
            continue
        for ln in ax.get_lines():
            add(ln.get_color())
        for p in ax.patches:
            add(p.get_facecolor())
        for coll in ax.collections:
            for c in list(coll.get_facecolor()) + list(coll.get_edgecolor()):
                add(tuple(c))
        for t in ax.texts:
            add(t.get_color())
    for t in fig.texts:
        add(t.get_color())
    return found


def cmyk_manifest(fig, theme: Theme | None = None) -> str:
    """A prepress sidecar: colours used, with their declared CMYK builds."""
    t = theme or get_theme()
    lines = [
        f"# hegevis colour manifest - theme: {t.name}",
        "# RGB is what the PDF contains; CMYK is the build the art desk declared",
        "# in the theme file. Anything marked UNDECLARED needs a decision before",
        "# it goes to press.",
        "",
    ]
    undeclared = []
    for hexval in sorted(colors_used(fig)):
        build = t.cmyk.get(hexval)
        if build:
            c, m, y, k = build
            lines.append(f"{hexval}    C{c:>3} M{m:>3} Y{y:>3} K{k:>3}")
        else:
            lines.append(f"{hexval}    UNDECLARED")
            undeclared.append(hexval)
    if undeclared:
        lines += ["", f"# {len(undeclared)} colour(s) have no declared CMYK build."]
    return "\n".join(lines) + "\n"


def _verify_embedded_fonts(path: Path) -> None:
    """A PDF that does not embed its type will reflow on someone else's machine."""
    try:
        blob = path.read_bytes()
    except OSError:
        return
    if b"/FontFile" not in blob:
        warnings.warn(
            f"{path.name}: no embedded font found. Text may reflow or substitute "
            "on another machine. Check rcParams['pdf.fonttype'] == 42.",
            stacklevel=3,
        )


def save(fig, path, *, manifest=False, outline_text=False, theme=None,
         verify=True, **kwargs):
    """Save a figure for print.

    Parameters
    ----------
    manifest : bool
        Also write ``<name>.colors.txt`` for prepress.
    outline_text : bool
        SVG only -- convert text to outlines instead of leaving it live. Use
        when the printer will not have the brand font; leave off when the
        design desk wants to edit the text in Illustrator.
    verify : bool
        For PDF, check the type actually embedded.

    Never passes ``bbox_inches="tight"``: the figure was built at true column
    width, and a tight box would silently change it.

    The masthead mark is asserted here as well as in ``finish()``, so a figure
    that skipped the house furniture -- a bare ``plt.subplots()`` an analyst
    saved through this function -- still leaves with the mark on it.
    """
    t = theme or get_theme()
    _logo.stamp(fig, t)
    path = Path(path)
    suffix = path.suffix.lower()
    if not suffix:
        path = path.with_suffix(".pdf")
        suffix = ".pdf"
    if suffix not in VECTOR:
        warnings.warn(
            f"{suffix} is a raster format; this package is set up for print vector "
            "output (.pdf, .svg, .eps). Saving anyway at 600dpi.",
            stacklevel=2,
        )
    if kwargs.get("bbox_inches") == "tight":
        warnings.warn(
            "bbox_inches='tight' changes the figure width, so the chart will not "
            "land at the column width it was built for. Ignoring it.",
            stacklevel=2,
        )
        kwargs.pop("bbox_inches")

    path.parent.mkdir(parents=True, exist_ok=True)
    # Pin the output params here rather than trusting whatever rcParams the
    # script left behind: font embedding is not optional for print.
    overrides = output_params(t)
    if outline_text and suffix == ".svg":
        overrides["svg.fonttype"] = "path"
    with mpl.rc_context(overrides):
        fig.savefig(path, facecolor=t.surface, edgecolor="none", **kwargs)

    if verify and suffix == ".pdf":
        _verify_embedded_fonts(path)

    written = [path]
    if manifest:
        side = path.with_suffix(path.suffix + ".colors.txt")
        side.write_text(cmyk_manifest(fig, t))
        written.append(side)
    return written


def simulate_figure(fig, kind: str = "deutan"):
    """Recolour a figure IN PLACE to proof it under colour-vision deficiency.

    Destructive -- save the real figure first, then simulate, then save the
    proof. ``kind`` is "protan", "deutan" or "tritan".

    The masthead mark is left alone: the proof asks whether the *data* can be
    told apart, and a brand mark that reads differently is not a chart fault.
    """
    def conv(c):
        try:
            return simulate_hex(to_hex(c), kind)
        except (ValueError, TypeError):
            return None

    for ax in fig.get_axes():
        if _logo.is_logo_axes(ax):
            continue
        for ln in ax.get_lines():
            new = conv(ln.get_color())
            if new:
                ln.set_color(new)
        for p in ax.patches:
            new = conv(p.get_facecolor())
            if new:
                p.set_facecolor(new)
        for coll in ax.collections:
            fc = coll.get_facecolor()
            if len(fc):
                coll.set_facecolor([conv(c) or "#000000" for c in fc])
    return fig
