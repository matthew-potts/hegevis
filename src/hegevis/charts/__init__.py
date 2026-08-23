"""House chart forms. Each takes an ``ax`` and returns it, so they compose with
plain matplotlib -- drop to raw mpl for anything the helpers do not cover."""

from .bars import grouped, ranked, share, stacked
from .timeseries import add_end_labels, area, index_to, line, shade_period

__all__ = [
    "add_end_labels", "area", "index_to", "line", "shade_period",
    "grouped", "ranked", "share", "stacked",
]
