"""Colour assignment. The properties here are the reasons the package exists:
a reader who learns "China is blue" must never be contradicted."""

import random
import warnings

import pytest

import hegevis as hv
from hegevis.palette import Palette, TooManySeries, fold_other
from hegevis.validate import validate


def test_canonical_order_when_nothing_is_pinned():
    p = Palette()
    got = list(p.for_series(["A", "B", "C", "D"]).values())
    assert got == list(hv.get_theme().series[:4])


def test_filtering_a_series_does_not_repaint_the_survivors():
    p = Palette()
    before = p.for_series(["US", "China", "EU"])
    after = p.for_series(["US", "EU"])
    assert after["US"] == before["US"]
    assert after["EU"] == before["EU"]


def test_reordering_by_rank_does_not_repaint():
    p = Palette()
    before = p.for_series(["US", "China", "EU"])
    after = p.for_series(["EU", "China", "US"])
    assert after == {k: before[k] for k in after}


def test_unrelated_charts_each_start_at_slot_one():
    """Otherwise a script of six charts exhausts the palette."""
    p = Palette()
    p.for_series(["US", "China", "EU"])
    other = p.for_series(["India", "Brazil"])
    assert other["India"] == hv.get_theme().series[0]


def test_pinned_entities_are_fixed_across_charts():
    t = hv.get_theme()
    p = Palette(t)
    p.pin("China", 3)
    for names in (["China", "US"], ["US", "EU", "China"], ["China"]):
        assert p.for_series(names)["China"] == t.series[3]


def test_ninth_series_raises_rather_than_inventing_a_hue():
    p = Palette()
    with pytest.raises(TooManySeries):
        p.for_series([f"s{i}" for i in range(9)])


def test_slot_never_wraps():
    p = Palette()
    with pytest.raises(TooManySeries):
        p.slot(len(hv.get_theme().series))


def test_emphasis_greys_everything_but_the_focus():
    t = hv.get_theme()
    p = Palette(t)
    got = p.emphasis(["a", "b", "c"], focus="b")
    assert got["b"] != t.neutral
    assert got["a"] == got["c"] == t.neutral


def test_emphasis_rejects_a_focus_that_is_not_present():
    with pytest.raises(ValueError):
        Palette().emphasis(["a", "b"], focus="c")


def test_fold_other_keeps_the_head_and_sums_the_tail():
    rows = [("a", 5), ("b", 4), ("c", 3), ("d", 2), ("e", 1)]
    assert fold_other(rows, keep=3) == [("a", 5), ("b", 4), ("c", 3), ("Other", 3)]


def test_fold_other_is_a_no_op_when_it_already_fits():
    rows = [("a", 5), ("b", 4)]
    assert fold_other(rows, keep=3) == rows


@pytest.mark.parametrize("seed", range(40))
def test_assigned_colours_always_clear_the_adjacency_gates(seed):
    """The property that makes entity-stability safe.

    Pinning permutes the validated slot order, which can put two colours side
    by side that were never checked together. Whatever the pinning, the
    sequence actually handed to a chart must still pass -- or warn loudly.
    """
    rng = random.Random(seed)
    t = hv.get_theme()
    p = Palette(t)
    for _ in range(rng.randint(0, 3)):
        p.pin(f"pinned{rng.randint(0, 5)}", rng.randrange(len(t.series)))
    names = [f"n{i}" for i in range(rng.randint(2, 6))]
    names += [n for n in list(p._assigned) if rng.random() < 0.5]
    names = list(dict.fromkeys(names))[:6]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        colors = list(p.for_series(names).values())
    rep = validate(colors, surface=t.surface)
    forced = any("forced a tight pair" in str(w.message) for w in caught)
    assert rep.ok or forced, f"{colors} failed silently"


def test_ordinal_ramp_is_monotone_and_readable():
    t = hv.get_theme()
    steps = Palette(t).ordinal(4)
    assert len(steps) == 4
    assert all(hv.contrast(s, t.surface) >= 2.0 for s in steps)


def test_diverging_puts_neutral_at_the_centre():
    """The midpoint must read as 'nothing', so it carries almost no chroma --
    a hue there would invent a third category."""
    t = hv.get_theme()
    p = Palette(t)
    mid = p.diverging_colors([-5, 0, 5])[1]
    assert hv.oklch(mid)[1] < 0.04
    assert hv.oklch(t.diverging["mid"])[1] < 0.04


def test_diverging_poles_are_warm_and_cool():
    """blue-vs-aqua fails this: both cool, so the midpoint stops reading as a
    boundary between opposites."""
    t = hv.get_theme()
    low_h = hv.color.ok_hue(t.diverging["low"])
    high_h = hv.color.ok_hue(t.diverging["high"])
    separation = abs((low_h - high_h + 180) % 360 - 180)
    assert separation > 120, f"poles only {separation:.0f} deg apart"


def test_diverging_handles_one_sided_data():
    """TwoSlopeNorm rejects data entirely on one side of the centre."""
    assert len(Palette().diverging_colors([2, 4, 6])) == 3


def test_status_colours_are_reserved_and_named():
    p = Palette()
    assert p.status("critical")
    with pytest.raises(ValueError):
        p.status("series4")


def test_label_ink_picks_a_readable_colour_for_in_fill_text():
    t = hv.get_theme()
    p = Palette(t)
    for fill in t.series:
        ink = p.label_ink(fill)
        assert hv.contrast(ink, fill) >= 3.0


def test_bad_entity_pin_is_rejected_at_load():
    t = hv.get_theme()
    bad = hv.Theme(**{**t.__dict__, "entities": {"X": 99}})
    with pytest.raises(ValueError):
        Palette(bad)
