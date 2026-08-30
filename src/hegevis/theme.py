"""Loading the house theme.

The theme is data, not code: it lives in ``house_theme.toml`` so the art desk
can change the palette or the column widths without reading Python. This module
turns that file into a frozen object the rest of the package reads.

Resolution order (first hit wins):

1. an explicit path passed to :func:`load_theme`
2. ``$HEGEVIS_THEME``
3. ``hegevis-theme.toml`` in the current working directory -- lets a single
   article or a special section override the house look without forking
4. the packaged ``house_theme.toml``
"""

from __future__ import annotations

import os
import tomllib
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from .color import BadColor, is_hex_color, strip_ws

PACKAGED = Path(__file__).with_name("house_theme.toml")
PROJECT_FILENAME = "hegevis-theme.toml"

MM = 1 / 25.4  # millimetres -> inches, matplotlib's unit


@dataclass(frozen=True)
class TypeScale:
    """Four sizes, and only one of them is used inside the plot.

    The old scale had separate axis/tick/label/legend sizes that all happened
    to be 7.5pt anyway. Naming them separately invited them to drift apart,
    which is how a chart ends up with four text sizes and no hierarchy. There
    is now one ``body`` size for everything in the plot area; ``axis``,
    ``tick``, ``label`` and ``legend`` remain as aliases so existing code and
    themes keep working, but they all report ``body``.
    """

    title: float = 10.0
    subtitle: float = 8.5
    body: float = 7.0
    footnote: float = 5.5

    @property
    def axis(self) -> float:
        return self.body

    @property
    def tick(self) -> float:
        return self.body

    @property
    def label(self) -> float:
        return self.body

    @property
    def legend(self) -> float:
        return self.body

    @property
    def source(self) -> float:
        return self.footnote


@dataclass(frozen=True)
class Tab:
    """The solid rectangle that opens every chart, top-left above the title.

    Its colour lives here rather than beside the data colours because it is
    never a data colour: it is a fixed piece of masthead, the same on every
    chart, and putting it in the series list would invite someone to use it.
    """

    width_mm: float = 14.0
    height_mm: float = 2.2
    top_mm: float = 4.5
    color: str = "#d1703a"


@dataclass(frozen=True)
class TextLimits:
    """Word ceilings for the furniture, warned about rather than truncated.

    Cutting an analyst's title silently would be worse than shipping a long
    one; the warning puts the decision back where it belongs.
    """

    title_words: int = 8
    subtitle_words: int = 14
    footnote_words: int = 20


@dataclass(frozen=True)
class Margin:
    left: float = 14.0
    right: float = 6.0
    top: float = 12.0
    bottom: float = 11.0


@dataclass(frozen=True)
class Layout:
    col1: float = 88.0
    col15: float = 120.0
    col2: float = 180.0
    page: float = 180.0
    default_ratio: float = 1.15  # portrait: a chart is a box, taller than wide
    margin: Margin = field(default_factory=Margin)

    def width_mm(self, size) -> float:
        """Accept a named column ('col1') or a literal width in millimetres."""
        if isinstance(size, (int, float)):
            return float(size)
        try:
            return float(getattr(self, size))
        except AttributeError:
            names = ", ".join(k for k in ("col1", "col15", "col2", "page"))
            raise ValueError(
                f"unknown size {size!r} - use one of {names}, or a width in mm"
            ) from None


@dataclass(frozen=True)
class Theme:
    name: str = "unnamed"
    family: tuple[str, ...] = ("DejaVu Sans",)
    title_family: tuple[str, ...] = ()
    weight_normal: int = 400
    weight_medium: int = 500
    weight_bold: int = 600
    size: TypeScale = field(default_factory=TypeScale)

    surface: str = "#fcfcfb"
    page: str = "#f9f9f7"
    ink: str = "#0b0b0b"
    ink_soft: str = "#52514e"
    ink_muted: str = "#898781"
    grid: str = "#e1e0d9"
    axis: str = "#c3c2b7"
    neutral: str = "#898781"

    series: tuple[str, ...] = ()
    sequential: tuple[str, ...] = ()
    diverging: dict = field(default_factory=dict)
    status: dict = field(default_factory=dict)
    entities: dict = field(default_factory=dict)
    layout: Layout = field(default_factory=Layout)
    tab: Tab = field(default_factory=Tab)
    text: TextLimits = field(default_factory=TextLimits)
    cmyk: dict = field(default_factory=dict)
    source_path: Path | None = None

    @property
    def titles(self) -> tuple[str, ...]:
        return self.title_family or self.family


def _hexes(values, where: str) -> tuple[str, ...]:
    out = []
    for v in values:
        c = strip_ws(str(v))
        if not is_hex_color(c):
            raise BadColor(f"{where}: invalid hex value {v!r} - expected #rrggbb")
        out.append(c if c.startswith("#") else f"#{c}")
    return tuple(out)


def _hex(value, where: str) -> str:
    return _hexes([value], where)[0]


def read_theme(path: str | Path) -> Theme:
    """Parse a theme TOML file into a :class:`Theme`. Raises on a bad colour."""
    path = Path(path)
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    t = raw.get("type", {})
    sizes = t.get("size", {})
    c = raw.get("color", {})
    lay = raw.get("layout", {})
    marg = lay.get("margin", {})
    tb = raw.get("tab", {})
    txt = raw.get("text", {})

    known = {f.name for f in (TypeScale.__dataclass_fields__.values())}
    # The per-role sizes collapsed into one `body`. A theme still naming them
    # is not broken, it is out of date, and silently ignoring the keys would
    # leave someone wondering why their edit did nothing.
    retired = {"axis", "tick", "label", "legend", "source"}
    stale = retired & set(sizes)
    if stale:
        warnings.warn(
            f"{path.name}: [type.size] {', '.join(sorted(stale))} no longer exist - "
            "everything inside the plot is one size now, set [type.size] body "
            "(and footnote for the source line).",
            stacklevel=2,
        )
    unknown = set(sizes) - known - retired
    if unknown:
        warnings.warn(
            f"{path.name}: ignoring unknown [type.size] key(s): {', '.join(sorted(unknown))}",
            stacklevel=2,
        )

    return Theme(
        name=raw.get("name", path.stem),
        family=tuple(t.get("family", ["DejaVu Sans"])),
        title_family=tuple(t.get("title_family", [])),
        weight_normal=t.get("weight_normal", 400),
        weight_medium=t.get("weight_medium", 500),
        weight_bold=t.get("weight_bold", 600),
        size=TypeScale(**{k: float(v) for k, v in sizes.items() if k in known}),
        surface=_hex(c.get("surface", "#fcfcfb"), "color.surface"),
        page=_hex(c.get("page", "#f9f9f7"), "color.page"),
        ink=_hex(c.get("ink", "#0b0b0b"), "color.ink"),
        ink_soft=_hex(c.get("ink_soft", "#52514e"), "color.ink_soft"),
        ink_muted=_hex(c.get("ink_muted", "#898781"), "color.ink_muted"),
        grid=_hex(c.get("grid", "#e1e0d9"), "color.grid"),
        axis=_hex(c.get("axis", "#c3c2b7"), "color.axis"),
        neutral=_hex(c.get("neutral", "#898781"), "color.neutral"),
        series=_hexes(c.get("series", []), "color.series"),
        sequential=_hexes(c.get("sequential", []), "color.sequential"),
        diverging={k: _hex(v, f"color.diverging.{k}")
                   for k, v in c.get("diverging", {}).items()},
        status={k: _hex(v, f"color.status.{k}")
                for k, v in c.get("status", {}).items()},
        entities={str(k): int(v) for k, v in raw.get("entities", {}).items()},
        layout=Layout(
            col1=float(lay.get("col1", 88.0)),
            col15=float(lay.get("col15", 120.0)),
            col2=float(lay.get("col2", 180.0)),
            page=float(lay.get("page", 180.0)),
            default_ratio=float(lay.get("default_ratio", 0.618)),
            margin=Margin(
                left=float(marg.get("left", 14.0)),
                right=float(marg.get("right", 6.0)),
                top=float(marg.get("top", 12.0)),
                bottom=float(marg.get("bottom", 11.0)),
            ),
        ),
        tab=Tab(
            width_mm=float(tb.get("width_mm", 14.0)),
            height_mm=float(tb.get("height_mm", 2.2)),
            top_mm=float(tb.get("top_mm", 4.5)),
            # Declared with the colours, where an art director looks for it.
            color=_hex(c.get("tab", "#d1703a"), "color.tab"),
        ),
        text=TextLimits(
            title_words=int(txt.get("title_words", 8)),
            subtitle_words=int(txt.get("subtitle_words", 14)),
            footnote_words=int(txt.get("footnote_words", 20)),
        ),
        cmyk={strip_ws(k).lower(): tuple(v) for k, v in raw.get("cmyk", {}).items()},
        source_path=path,
    )


def _discover() -> Path:
    env = os.environ.get("HEGEVIS_THEME")
    if env:
        p = Path(env).expanduser()
        if not p.is_file():
            raise FileNotFoundError(f"$HEGEVIS_THEME points at {p}, which does not exist")
        return p
    local = Path.cwd() / PROJECT_FILENAME
    if local.is_file():
        return local
    return PACKAGED


_current: Theme | None = None


def load_theme(path: str | Path | None = None) -> Theme:
    """Load (and make current) a theme. ``None`` runs the discovery order."""
    global _current
    _current = read_theme(path if path is not None else _discover())
    _reset_palette()
    return _current


def get_theme() -> Theme:
    """The current theme, loading it on first use."""
    return _current if _current is not None else load_theme()


def set_theme(theme: Theme) -> Theme:
    """Install an already-built :class:`Theme` (used by tests and previews)."""
    global _current
    _current = theme
    _reset_palette()
    return _current


def _reset_palette() -> None:
    """Clear the session colour registry. Imported late to avoid a cycle."""
    from .palette import reset_palette
    reset_palette()
