"""House chart forms. Each takes an ``ax`` and returns it, so they compose with
plain matplotlib -- drop to raw mpl for anything the helpers do not cover.

Five forms, deliberately. Bars for magnitude (``ranked``, ``columns``) and
distribution (``histogram``); lines for change over time (``line``) and change
between two moments (``slope``). Anything that is not a bar or a line is not a
house form, which is why area, stacked and 100%-stacked bars are gone.

The annotation helpers -- ``index_to``, ``shade_period``, ``add_end_labels``,
``fold_other`` -- are not forms and are unaffected: they make the five forms
readable.
"""

from .bars import columns, histogram, ranked
from .timeseries import add_end_labels, index_to, line, shade_period, slope

__all__ = [
    # forms
    "ranked", "columns", "histogram", "line", "slope",
    # helpers
    "add_end_labels", "index_to", "shade_period",
]
