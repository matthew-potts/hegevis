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


def test_only_bar_and_line_forms_are_offered():
    """The v2 surface is five forms. Area, stacked, share and grouped bars were
    removed on purpose -- each asked a reader to compare lengths that do not
    share a baseline, which is the one comparison bars are good at."""
    assert not [n for n in ("area", "stacked", "share", "grouped")
                if hasattr(hv, n)]
    assert all(hasattr(hv, n) for n in
               ("ranked", "columns", "histogram", "line", "slope"))


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


# -- ordered columns -----------------------------------------------------------

def test_columns_order_biggest_first_left_to_right():
    """The direction a reader scans, so the ranking is legible without effort."""
    fig, ax = hv.figure("col1")
    hv.columns(ax, ["a", "b", "c"], [1, 3, 2])
    assert [t.get_text() for t in ax.get_xticklabels()] == ["b", "c", "a"]


def test_columns_keep_other_at_the_end_whatever_its_size():
    fig, ax = hv.figure("col1")
    hv.columns(ax, ["a", "Other", "c"], [3, 99, 1])
    assert [t.get_text() for t in ax.get_xticklabels()][-1] == "Other"


def test_columns_use_one_colour_unless_told_to_highlight():
    fig, ax = hv.figure("col1")
    hv.columns(ax, ["a", "b", "c"], [3, 2, 1])
    assert len({tuple(p.get_facecolor()) for p in ax.patches}) == 1

    fig2, ax2 = hv.figure("col1")
    hv.columns(ax2, ["a", "b", "c"], [3, 2, 1], highlight="a")
    assert len({tuple(p.get_facecolor()) for p in ax2.patches}) == 2


# -- histogram -----------------------------------------------------------------

def test_histogram_keeps_the_number_line_in_order():
    """Sorting a histogram by height would destroy the shape that is the point."""
    fig, ax = hv.figure("col1")
    hv.histogram(ax, [1, 1, 1, 2, 2, 9], bins=3)
    centres = [p.get_x() for p in ax.patches]
    assert centres == sorted(centres)


def test_histogram_bins_are_separated_by_the_ground_not_a_stroke():
    fig, ax = hv.figure("col1")
    hv.histogram(ax, list(range(50)), bins=5)
    assert all(p.get_linewidth() == 0 for p in ax.patches)
    widths = [p.get_width() for p in ax.patches]
    edges = np.histogram(list(range(50)), bins=5)[1]
    assert all(w < np.diff(edges)[0] for w in widths)  # the gap came out of the bar


def test_histogram_rejects_an_empty_series():
    fig, ax = hv.figure("col1")
    with pytest.raises(ValueError, match="at least one finite value"):
        hv.histogram(ax, [float("nan"), float("inf")])


# -- slope ---------------------------------------------------------------------

def test_slope_draws_one_line_per_series_between_two_points():
    fig, ax = hv.figure("col1")
    hv.slope(ax, {"a": (1, 5), "b": (4, 2)})
    assert len(ax.get_lines()) == 2
    assert all(list(ln.get_xdata()) == [0, 1] for ln in ax.get_lines())


def test_slope_refuses_anything_other_than_two_periods():
    fig, ax = hv.figure("col1")
    with pytest.raises(ValueError, match="exactly two values"):
        hv.slope(ax, {"a": (1, 2, 3)})


def test_slope_labels_both_ends_and_keeps_them_inside_the_box():
    """Both ends carry a label, and the margins widen so nothing is clipped."""
    fig, ax = hv.figure("col1")
    hv.slope(ax, {"United States of America": (1, 5), "b": (4, 2)},
             labels=["2019", "2030"])
    texts = [a.get_text() for a in ax.texts]
    assert any("United States of America" in s for s in texts)
    assert fig._hegevis_label_left_in > 0
    assert fig._hegevis_label_right_in > 0


def test_slope_draws_no_value_scale():
    """The lines are the comparison; a y-axis would invite a reader to measure
    levels off a form built to show change."""
    fig, ax = hv.figure("col1")
    hv.slope(ax, {"a": (1, 5)})
    assert not any(lbl.get_visible() and lbl.get_text()
                   for lbl in ax.get_yticklabels())
