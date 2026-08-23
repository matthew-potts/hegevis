"""Turning whatever the analyst has into (x, {name: values}).

Analysts arrive with a DataFrame, a dict of lists, or bare arrays. Normalising
here means every chart helper accepts all three and none of them has to care.
"""

from __future__ import annotations

import numpy as np


def _is_dataframe(obj) -> bool:
    return hasattr(obj, "columns") and hasattr(obj, "index")


def as_series(data, x=None, y=None):
    """Return ``(x_values, {name: np.ndarray})``.

    Accepts a DataFrame (wide: one column per series), a mapping of
    name -> values, or a single sequence.
    """
    if _is_dataframe(data):
        if x is None:
            xs = data.index.to_numpy()
            cols = list(y) if y is not None else list(data.columns)
        else:
            xs = data[x].to_numpy()
            cols = list(y) if y is not None else [c for c in data.columns if c != x]
        missing = [c for c in cols if c not in data.columns]
        if missing:
            raise KeyError(f"column(s) not in the frame: {missing}")
        return xs, {str(c): data[c].to_numpy(dtype=float) for c in cols}

    if isinstance(data, dict):
        if x is None:
            raise ValueError("pass x= alongside a dict of series")
        return np.asarray(x), {str(k): np.asarray(v, dtype=float) for k, v in data.items()}

    values = np.asarray(data, dtype=float)
    if values.ndim != 1:
        raise ValueError("a bare sequence must be 1-D; use a dict or DataFrame for several series")
    if x is None:
        x = np.arange(len(values))
    name = y if isinstance(y, str) else "value"
    return np.asarray(x), {name: values}


def last_valid(xs, ys):
    """The last point that is not NaN -- where an end label belongs."""
    finite = np.flatnonzero(np.isfinite(ys))
    if not len(finite):
        return None
    i = finite[-1]
    return xs[i], ys[i]
