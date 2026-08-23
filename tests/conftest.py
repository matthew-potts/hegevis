import matplotlib
matplotlib.use("Agg")

import pytest

import hegevis as hv


@pytest.fixture(autouse=True)
def fresh_theme():
    """Each test gets an untouched theme and an empty colour registry."""
    hv.load_theme()
    yield
    hv.load_theme()


@pytest.fixture(autouse=True)
def close_figures():
    yield
    import matplotlib.pyplot as plt
    plt.close("all")
