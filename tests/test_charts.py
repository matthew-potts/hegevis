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
    """The surface is seven forms. Area, stacked, share and grouped bars were
    removed on purpose -- each asked a reader to compare lengths that do not
    share a baseline, which is the one comparison bars are good at."""
    assert not [n for n in ("area", "stacked", "share", "grouped")
                if hasattr(hv, n)]
    assert all(hasattr(hv, n) for n in
               ("ranked", "columns", "histogram", "line", "slope", "dumbbell",
                "timeline"))


# -- timeline ------------------------------------------------------------------

def test_timeline_writes_each_date_once_and_every_value():
    fig, ax = hv.figure("col1")
    hv.timeline(ax, [("2019", "60", "launched"), ("2025", "$11bn", "revenue"),
                     ("2025", "61%", "of group revenue")])
    texts = [t.get_text() for t in ax.texts]
    assert texts.count("2025") == 1
    assert {"60", "$11bn", "61%"} <= set(texts)


def test_timeline_wraps_long_descriptions_inside_the_figure():
    fig, ax = hv.figure("col1")
    hv.timeline(ax, [("2026", "64%", "of subscribers are in a long list of "
                                      "countries that will not fit on one line")])
    fig.canvas.draw()
    assert len(ax.texts) > 3
    for text in ax.texts:
        assert text.get_window_extent().x1 <= fig.bbox.width


def test_timeline_warns_when_the_milestones_do_not_fit():
    fig, ax = hv.figure("col1", height=50)
    with pytest.warns(UserWarning, match="taller"):
        hv.timeline(ax, [(str(y), "1", "x") for y in range(20)])


def test_timeline_refuses_an_empty_list():
    fig, ax = hv.figure("col1")
    with pytest.raises(ValueError):
        hv.timeline(ax, [])


# -- dumbbell ------------------------------------------------------------------

def test_dumbbell_draws_two_dots_and_a_rule_per_row():
    fig, ax = hv.figure("col1")
    hv.dumbbell(ax, {"a": (1, 3), "b": (2, 5)})
    assert len(ax.collections[0].get_segments()) == 2
    assert [len(l.get_xdata()) for l in ax.lines] == [2, 2]


def test_dumbbell_puts_the_largest_end_value_on_top_unless_told_not_to():
    fig, ax = hv.figure("col1")
    hv.dumbbell(ax, {"a": (1, 9), "b": (2, 5)})
    assert [t.get_text() for t in ax.get_yticklabels()][-1] == "a"
    fig, ax = hv.figure("col1")
    hv.dumbbell(ax, {"b": (2, 5), "a": (1, 9)}, sort=False)
    assert [t.get_text() for t in ax.get_yticklabels()][-1] == "b"


def test_dumbbell_names_the_periods_on_the_top_row_not_in_a_legend():
    fig, ax = hv.figure("col1")
    hv.dumbbell(ax, {"a": (1, 3)}, labels=["2019", "2024"])
    assert {t.get_text() for t in ax.texts} == {"2019", "2024"}
    assert ax.get_legend() is None


def test_dumbbell_refuses_anything_other_than_two_values():
    fig, ax = hv.figure("col1")
    with pytest.raises(ValueError):
        hv.dumbbell(ax, {"a": (1, 2, 3)})


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


def test_ranked_caps_the_gap_between_a_few_bars():
    """Three bars should cluster, not spread across the whole box."""
    from hegevis.charts.bars import MAX_SLOT_MM, _axis_extent_mm
    fig, ax = hv.figure("col1")
    hv.ranked(ax, ["a", "b", "c"], [3, 2, 1])
    lo, hi = ax.get_ylim()
    pitch_mm = _axis_extent_mm(ax, "y") / (hi - lo)
    assert pitch_mm == pytest.approx(MAX_SLOT_MM)
    # Padded evenly, so the cluster sits mid-plot.
    assert (lo + hi) / 2 == pytest.approx(1.0)


def test_ranked_leaves_a_long_ranking_on_its_natural_pitch():
    from hegevis.charts.bars import MAX_SLOT_MM, _axis_extent_mm
    fig, ax = hv.figure("col1")
    n = 20
    hv.ranked(ax, [str(i) for i in range(n)], range(n))
    lo, hi = ax.get_ylim()
    assert _axis_extent_mm(ax, "y") / (hi - lo) < MAX_SLOT_MM


def test_ranked_tip_labels_follow_their_bars_through_the_sort():
    fig, ax = hv.figure("col1")
    hv.ranked(ax, ["a", "b", "c"], [1, 3, 2], tip_labels=["~1", "~3", "~2"])
    tips = {round(t.xy[1]): t.get_text() for t in ax.texts}
    names = [t.get_text() for t in ax.get_yticklabels()]
    assert {names[p]: s for p, s in tips.items()} == {"a": "~1", "b": "~3", "c": "~2"}


def test_ranked_rejects_tip_labels_that_do_not_match_the_bars():
    fig, ax = hv.figure("col1")
    with pytest.raises(ValueError):
        hv.ranked(ax, ["a", "b"], [1, 2], tip_labels=["x"])


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
    # Short end labels can fit in the theme margin, so test the outcome -- every
    # label inside the figure -- rather than that extra room was reserved.
    fig.canvas.draw()
    width = fig.bbox.width
    for text in ax.texts:
        ext = text.get_window_extent()
        assert ext.x0 >= 0 and ext.x1 <= width


def test_slope_value_labels_replace_the_printed_values():
    fig, ax = hv.figure("col1")
    hv.slope(ax, {"a": (0.2, 1.0), "b": (0.5, 0.6)},
             value_labels={"a": ("0.1-0.3%", "1% (5x)")})
    texts = {t.get_text() for t in ax.texts}
    assert {"a  0.1-0.3%", "1% (5x)"} <= texts
    # Series not named keep their formatted values.
    assert "b  0.5" in texts


def test_slope_rejects_value_labels_for_unknown_series():
    fig, ax = hv.figure("col1")
    with pytest.raises(ValueError):
        hv.slope(ax, {"a": (1, 2)}, value_labels={"z": ("x", "y")})


def test_slope_value_axis_keeps_start_labels_inside_the_plot():
    fig, ax = hv.figure("col1")
    hv.slope(ax, {"A long series name": (1, 2), "b": (2, 3)}, value_axis=True)
    assert ax.yaxis.get_tick_params()["labelleft"]
    fig.canvas.draw()
    box = ax.get_window_extent()
    for text in ax.texts:
        ext = text.get_window_extent()
        assert ext.x0 >= box.x0 - 1


def test_slope_can_name_the_lines_at_the_end():
    fig, ax = hv.figure("col1")
    hv.slope(ax, {"a": (1, 2), "b": (2, 3)}, label_values=False, name_side="end")
    assert {t.get_text(): t.xy[0] for t in ax.texts} == {"a": 1.0, "b": 1.0}


def test_slope_draws_no_value_scale():
    """The lines are the comparison; a y-axis would invite a reader to measure
    levels off a form built to show change."""
    fig, ax = hv.figure("col1")
    hv.slope(ax, {"a": (1, 5)})
    assert not any(lbl.get_visible() and lbl.get_text()
                   for lbl in ax.get_yticklabels())
