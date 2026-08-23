"""Every v1 chart form, with illustrative (synthetic) geoeconomics data.

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


def timeseries_indexed():
    years = pd.period_range("2015", "2024", freq="Y").to_timestamp()
    df = pd.DataFrame({
        "China": _drift(len(years), 100, 3.4, 2.2),
        "United States": _drift(len(years), 100, 1.9, 1.8),
        "European Union": _drift(len(years), 100, 1.1, 2.0),
        "India": _drift(len(years), 100, 5.0, 2.6),
    }, index=years)

    fig, ax = hv.figure("col2", ratio=0.52)
    xs, indexed = hv.index_to(df)
    hv.line(ax, indexed, x=xs)
    hv.shade_period(ax, pd.Timestamp("2020-01-01"), pd.Timestamp("2021-06-01"),
                    label="Pandemic")
    ax.set_ylabel("Index, 2015 = 100")
    hv.finish(
        fig,
        title="Goods exports diverge after the pandemic",
        subtitle="Merchandise exports by reporter, indexed to 2015 = 100",
        source="Illustrative synthetic data",
        note="Shaded: Feb 2020 - Jun 2021.",
    )
    hv.save(fig, f"{OUT}/01-timeseries-indexed.pdf", manifest=True)
    fig.savefig(f"{OUT}/01-timeseries-indexed.png", dpi=200)
    return fig


def timeseries_emphasis():
    years = pd.period_range("2010", "2024", freq="Y").to_timestamp()
    names = ["Russia", "Brazil", "Turkey", "Indonesia", "South Africa"]
    df = pd.DataFrame(
        {n: _drift(len(years), 100, r, 3.0)
         for n, r in zip(names, [-1.2, 1.4, 0.6, 2.1, 0.3])},
        index=years,
    )

    fig, ax = hv.figure("col1", ratio=0.72)
    hv.line(ax, df, emphasis="Russia")
    ax.set_ylabel("Share of G20 trade, index")
    hv.finish(
        fig,
        title="Russia's trade share falls away",
        subtitle="Selected G20 economies, 2010 = 100",
        source="Illustrative synthetic data",
    )
    hv.save(fig, f"{OUT}/02-emphasis.pdf")
    fig.savefig(f"{OUT}/02-emphasis.png", dpi=200)
    return fig


def ranked_bars():
    data = {
        "China": 3380, "United States": 2020, "Germany": 1690, "Netherlands": 940,
        "Japan": 917, "South Korea": 683, "Italy": 676, "France": 648,
        "Belgium": 633, "Mexico": 593,
    }
    kept = hv.fold_other(list(data.items()), keep=8)

    fig, ax = hv.figure("col1", ratio=1.05)
    hv.ranked(ax, [k for k, _ in kept], [v for _, v in kept],
              highlight="China", unit="")
    ax.set_xlabel("Goods exports, $bn")
    hv.finish(
        fig,
        title="China leads goods exports by a wide margin",
        subtitle="Merchandise exports, $bn",
        source="Illustrative synthetic data",
        note="Tail of the top 10 folded into 'Other'.",
    )
    hv.save(fig, f"{OUT}/03-ranked.pdf")
    fig.savefig(f"{OUT}/03-ranked.png", dpi=200)
    return fig


def grouped_columns():
    df = pd.DataFrame({
        "2019": [61.8, 20.6, 5.4, 4.4],
        "2024": [58.2, 19.8, 5.7, 5.9],
    }, index=["USD", "EUR", "JPY", "GBP"])

    fig, ax = hv.figure("col1", ratio=0.68)
    hv.grouped(ax, df)
    ax.set_ylabel("Share of allocated reserves, %")
    hv.finish(
        fig,
        title="Reserve shares move slowly",
        subtitle="Currency composition of allocated FX reserves, %",
        source="Illustrative synthetic data",
    )
    hv.save(fig, f"{OUT}/04-grouped.pdf")
    fig.savefig(f"{OUT}/04-grouped.png", dpi=200)
    return fig


def share_bars():
    df = pd.DataFrame({
        "Taiwan": [68, 62, 55],
        "South Korea": [12, 15, 17],
        "United States": [8, 11, 15],
        "Japan": [7, 7, 8],
        "Other": [5, 5, 5],
    }, index=["2019", "2024", "2030 (proj.)"])

    fig, ax = hv.figure("col2", ratio=0.42)
    hv.share(ax, df)
    hv.finish(
        fig,
        title="Leading-edge fabrication slowly diversifies",
        subtitle="Share of sub-7nm foundry capacity, %",
        source="Illustrative synthetic data",
    )
    hv.save(fig, f"{OUT}/05-share.pdf")
    fig.savefig(f"{OUT}/05-share.png", dpi=200)
    return fig


def stacked_columns():
    df = pd.DataFrame({
        "Tariffs": [12, 19, 31, 44, 51],
        "Export controls": [4, 9, 18, 33, 47],
        "Investment screening": [3, 6, 11, 16, 22],
    }, index=["2020", "2021", "2022", "2023", "2024"])

    fig, ax = hv.figure("col1", ratio=0.7)
    hv.stacked(ax, df, label_values=True)
    ax.set_ylabel("Measures in force")
    hv.finish(
        fig,
        title="Restrictive measures keep accumulating",
        subtitle="New measures in force, by instrument",
        source="Illustrative synthetic data",
    )
    hv.save(fig, f"{OUT}/06-stacked.pdf")
    fig.savefig(f"{OUT}/06-stacked.png", dpi=200)
    return fig


if __name__ == "__main__":
    import pathlib
    pathlib.Path(OUT).mkdir(parents=True, exist_ok=True)
    hv.use()
    for fn in (timeseries_indexed, timeseries_emphasis, ranked_bars,
               grouped_columns, share_bars, stacked_columns):
        fn()
        print("ok:", fn.__name__)
