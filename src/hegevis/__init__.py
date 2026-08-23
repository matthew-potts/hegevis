"""hegevis -- the house data-visualisation style.

Two levels, one look. Restyle an existing script::

    import matplotlib.pyplot as plt
    import hegevis as hv

    hv.use()                       # every chart below is now in the house style
    fig, ax = plt.subplots()
    ax.plot(...)

Or let the package do the furniture too::

    import hegevis as hv

    hv.use()
    fig, ax = hv.figure("col1")
    hv.line(ax, df)
    ax.set_ylabel("Index, 2015 = 100")
    hv.finish(fig, title="Trade reorients", subtitle="Goods exports, indexed",
              source="IMF Direction of Trade Statistics")
    hv.save(fig, "trade.pdf")

The house rules the package enforces for you, so nobody has to remember them:

* colour follows the entity, never its rank -- China is the same colour in
  every article, and filtering a series never repaints the survivors
* categorical hues are assigned in a fixed, colourblind-validated order and
  never cycled past the eighth slot
* no dual-axis charts -- use :func:`index_to` to put two magnitudes on one axis
* figures are built at true printed width, so type lands at the size it is set

Changing the look for everyone is one file: ``house_theme.toml``.
"""

from __future__ import annotations

from .charts import (
    add_end_labels, area, grouped, index_to, line, ranked, shade_period, share,
    stacked,
)
from .color import contrast, delta_e, oklch, simulate_hex
from .export import cmyk_manifest, colors_used, save, simulate_figure
from .layout import figure, finish
from .palette import Palette, TooManySeries, default_palette, fold_other
from .rc import rc_params, style, use
from .theme import Theme, get_theme, load_theme, set_theme
from .validate import PaletteError, validate, validate_ordinal

__version__ = "0.1.0"

__all__ = [
    # style
    "use", "style", "rc_params",
    # theme
    "Theme", "get_theme", "load_theme", "set_theme",
    # colour
    "Palette", "default_palette", "fold_other", "TooManySeries",
    "contrast", "delta_e", "oklch", "simulate_hex",
    # figures
    "figure", "finish",
    # charts
    "line", "area", "index_to", "shade_period", "add_end_labels",
    "ranked", "grouped", "stacked", "share",
    # output
    "save", "cmyk_manifest", "colors_used", "simulate_figure",
    # checks
    "validate", "validate_ordinal", "PaletteError",
    "__version__",
]


def palette() -> Palette:
    """The shared session palette -- what every chart helper uses by default."""
    return default_palette(get_theme())
