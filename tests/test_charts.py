"""Chart behaviour. Most of these guard a rule that is easy to break by
accident and hard to notice by eye."""

import numpy as np
import pytest

import hegevis as hv


@pytest.fixture
def frame():
    pd = pytest.importorskip("pandas")
    idx = pd.date_range("2015", periods=8, freq="YS")
    return pd.DataFrame(
        {"China": np.linspace(100, 160, 8),
         "United States": np.linspace(100, 118, 8),
         "European Union": np.linspace(100, 104, 8)},
        index=idx,
    )


def test_line_accepts_a_frame_a_dict_and_a_bare_sequence(frame):
    fig, ax = hv.figure("col1")
    hv.line(ax, frame)
    assert len(ax.get_lines()) == 3

    fig, ax = hv.figure("col1")
    hv.line(ax, {"a": [1, 2, 3], "b": [3, 2, 1]}, x=[0, 1, 2])
    assert len(ax.get_lines()) == 2

    fig, ax = hv.figure("col1")
    hv.line(ax, [1, 2, 3])
    assert len(ax.get_lines()) == 1


def test_index_to_rebases_every_series(frame):
    xs, out = hv.index_to(frame, base=100)
    for vals in out.values():
        assert vals[0] == pytest.approx(100.0)


def test_index_to_rejects_an_unusable_base(frame):
    frame.iloc[0, 0] = 0.0
    with pytest.raises(ValueError):
        hv.index_to(frame)


def test_end_labels_do_not_stretch_the_x_axis_past_the_data(frame):
    """Widening the axis to fit labels would let the tick locator imply data
    that does not exist."""
    fig, ax = hv.figure("col2")
    hv.line(ax, frame, label_ends=False)
    before = ax.get_xlim()
    fig2, ax2 = hv.figure("col2")
    hv.line(ax2, frame, label_ends=True)
    assert ax2.get_xlim() == pytest.approx(before)


def test_end_labels_reserve_figure_margin_instead(frame):
    fig, ax = hv.figure("col2")
    hv.line(ax, frame, label_ends=True)
    assert getattr(fig, "_hegevis_label_right_in", 0) > 0


def test_emphasis_greys_the_context_and_drops_the_legend(frame):
    t = hv.get_theme()
    fig, ax = hv.figure("col1")
    hv.line(ax, frame, emphasis="China")
    colors = {ln.get_label(): ln.get_color() for ln in ax.get_lines()}
    assert colors["United States"] == t.neutral
    assert colors["China"] != t.neutral
    # A legend of identical greys would promise a distinction that is not there.
    assert ax.get_legend() is None


def test_multi_line_charts_label_ends_by_default(frame):
    fig, ax = hv.figure("col2")
    hv.line(ax, frame)
    labelled = {a.get_text() for a in ax.texts}
    assert {"China", "United States", "European Union"} <= labelled


def test_area_refuses_more_than_one_series(frame):
    fig, ax = hv.figure("col1")
    with pytest.raises(ValueError, match="single series"):
        hv.area(ax, frame)


def test_area_draws_a_wash_not_a_block(frame):
    fig, ax = hv.figure("col1")
    hv.area(ax, frame[["China"]])
    fills = ax.collections
    assert fills and fills[0].get_alpha() <= 0.15


def test_shade_period_sits_behind_the_data(frame):
    fig, ax = hv.figure("col1")
    hv.line(ax, frame)
    band = hv.shade_period(ax, frame.index[2], frame.index[4], label="Episode")
    assert band.get_zorder() < min(ln.get_zorder() for ln in ax.get_lines())


def test_ranked_uses_one_colour_for_a_single_series():
    """Shading bars by value re-encodes what length already shows."""
    fig, ax = hv.figure("col1")
    hv.ranked(ax, ["a", "b", "c"], [3, 2, 1])
    assert len({tuple(p.get_facecolor()) for p in ax.patches}) == 1


def test_ranked_keeps_other_at_the_foot_whatever_its_size():
    fig, ax = hv.figure("col1")
    hv.ranked(ax, ["a", "Other", "c"], [3, 99, 1])
    assert [t.get_text() for t in ax.get_yticklabels()][0] == "Other"


def test_ranked_highlight_greys_the_rest():
    t = hv.get_theme()
    fig, ax = hv.figure("col1")
    hv.ranked(ax, ["a", "b", "c"], [3, 2, 1], highlight="a")
    assert len({tuple(p.get_facecolor()) for p in ax.patches}) == 2


def test_ranked_widens_the_left_margin_for_long_names():
    fig, ax = hv.figure("col1")
    hv.ranked(ax, ["United States of America", "b"], [2, 1])
    assert getattr(fig, "_hegevis_label_left_in", 0) > 0


def test_bars_are_capped_in_absolute_thickness():
    from hegevis.charts.bars import MAX_BAR_MM, _axis_extent_mm, _thickness
    fig, ax = hv.figure("col1", ratio=1.2)
    th = _thickness(ax, 3, "y")
    mm = th * _axis_extent_mm(ax, "y") / 3
    assert mm <= MAX_BAR_MM + 1e-9


def test_grouped_rejects_a_transposed_frame():
    with pytest.raises(ValueError, match="categories"):
        fig, ax = hv.figure("col1")
        hv.grouped(ax, {"a": [1, 2], "b": [3, 4]}, x=[1, 2, 3])


def test_stacked_only_labels_segments_that_fit():
    """A clipped or overflowing label is worse than no label."""
    fig, ax = hv.figure("col1")
    hv.stacked(ax, {"big": [100.0], "tiny": [0.4]}, x=["only"], label_values=True)
    texts = {t.get_text() for t in ax.texts}
    assert "100" in texts
    assert "0.4" not in texts


def test_share_normalises_to_100():
    fig, ax = hv.figure("col2")
    hv.share(ax, {"a": [1.0, 3.0], "b": [1.0, 1.0]}, x=["x", "y"])
    assert ax.get_xlim() == (0, 100)


def test_share_rejects_a_zero_total():
    fig, ax = hv.figure("col1")
    with pytest.raises(ValueError, match="positive total"):
        hv.share(ax, {"a": [0.0], "b": [0.0]}, x=["x"])


def test_legend_sits_above_the_plot_not_on_the_data():
    fig, ax = hv.figure("col1")
    hv.grouped(ax, {"a": [1, 2], "b": [2, 1]}, x=["p", "q"])
    leg = ax.get_legend()
    assert leg is not None
    assert leg.get_bbox_to_anchor().y0 >= ax.get_window_extent().y1 - 1
