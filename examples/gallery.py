"""Every v2 chart form, with illustrative (synthetic) geoeconomics data.

Five forms and no more: ranked rows, ordered columns, a histogram, a time
series and a slope chart.

Run: python examples/gallery.py
Writes PDFs to examples/out/ plus PNG proofs for on-screen review.
"""

import numpy as np
import pandas as pd

import hegevis as hv

OUT = "examples/out"
rng = np.random.default_rng(7)


def _drift(n, start, rate, vol):
    steps = rng.normal(rate, vol, n).cumsum()
    return start * np.exp(steps / 100)


def timeseries():
    years = pd.period_range("2015", "2024", freq="Y").to_timestamp()
    df = pd.DataFrame({
        "China": _drift(len(years), 100, 3.4, 2.2),
        "United States": _drift(len(years), 100, 1.9, 1.8),
        "European Union": _drift(len(years), 100, 1.1, 2.0),
    }, index=years)

    fig, ax = hv.figure("col1")
    xs, indexed = hv.index_to(df)
    hv.line(ax, indexed, x=xs)
    hv.shade_period(ax, pd.Timestamp("2020-01-01"), pd.Timestamp("2021-06-01"),
                    label="Pandemic")
    hv.finish(
        fig,
        title="Goods exports diverge",
        subtitle="Merchandise exports, 2015 = 100",
        source="Illustrative synthetic data",
    )
    hv.save(fig, f"{OUT}/01-timeseries.pdf")
    fig.savefig(f"{OUT}/01-timeseries.png", dpi=200)
    return fig


def emphasis():
    years = pd.period_range("2010", "2024", freq="Y").to_timestamp()
    names = ["Russia", "Brazil", "Turkey", "Indonesia"]
    df = pd.DataFrame(
        {n: _drift(len(years), 100, r, 3.0)
         for n, r in zip(names, [-1.2, 1.4, 0.6, 2.1])},
        index=years,
    )

    fig, ax = hv.figure("col1")
    hv.line(ax, df, emphasis="Russia")
    hv.finish(
        fig,
        title="Russia's trade share falls away",
        subtitle="Selected economies, 2010 = 100",
        source="Illustrative synthetic data",
    )
    hv.save(fig, f"{OUT}/02-emphasis.pdf")
    fig.savefig(f"{OUT}/02-emphasis.png", dpi=200)
    return fig


def ranked_rows():
    data = {
        "China": 3380, "United States": 2020, "Germany": 1690,
        "Netherlands": 940, "Japan": 917, "South Korea": 683, "Italy": 676,
    }
    fig, ax = hv.figure("col1")
    hv.ranked(ax, list(data), list(data.values()), highlight="China")
    hv.finish(
        fig,
        title="China leads goods exports",
        subtitle="Merchandise exports, $bn",
        source="Illustrative synthetic data",
    )
    hv.save(fig, f"{OUT}/03-ranked.pdf")
    fig.savefig(f"{OUT}/03-ranked.png", dpi=200)
    return fig


def ordered_columns():
    data = {"USD": 58.2, "EUR": 19.8, "JPY": 5.7, "GBP": 4.9, "CNY": 2.3}
    fig, ax = hv.figure("col1")
    hv.columns(ax, list(data), list(data.values()), unit="%")
    hv.finish(
        fig,
        title="The dollar still dominates reserves",
        subtitle="Share of allocated FX reserves, %",
        source="Illustrative synthetic data",
    )
    hv.save(fig, f"{OUT}/04-columns.pdf")
    fig.savefig(f"{OUT}/04-columns.png", dpi=200)
    return fig


def distribution():
    tariffs = np.concatenate([
        rng.gamma(2.0, 3.0, 400),
        rng.normal(22, 4, 60),
    ])
    fig, ax = hv.figure("col1")
    hv.histogram(ax, tariffs)
    ax.set_xlabel("Applied tariff rate, %")
    hv.finish(
        fig,
        title="Most tariffs are low, a few are not",
        subtitle="Applied MFN rates across tariff lines",
        source="Illustrative synthetic data",
    )
    hv.save(fig, f"{OUT}/05-histogram.pdf")
    fig.savefig(f"{OUT}/05-histogram.png", dpi=200)
    return fig


def slope_chart():
    data = {
        "Taiwan": (68, 55),
        "South Korea": (12, 17),
        "United States": (8, 15),
        "Japan": (7, 8),
    }
    fig, ax = hv.figure("col1")
    hv.slope(ax, data, labels=["2019", "2030"], unit="%",
             emphasis="United States")
    hv.finish(
        fig,
        title="Fabrication slowly diversifies",
        subtitle="Share of sub-7nm foundry capacity, %",
        source="Illustrative synthetic data",
    )
    hv.save(fig, f"{OUT}/06-slope.pdf")
    fig.savefig(f"{OUT}/06-slope.png", dpi=200)
    return fig


if __name__ == "__main__":
    import pathlib
    pathlib.Path(OUT).mkdir(parents=True, exist_ok=True)
    hv.use()
    for fn in (timeseries, emphasis, ranked_rows, ordered_columns,
               distribution, slope_chart):
        fn()
        print("ok:", fn.__name__)
