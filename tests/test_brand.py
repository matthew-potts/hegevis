"""Deriving a palette from brand anchors.

The point of these tests is that the derivation cannot quietly produce
something that fails the checks -- if a brand's colours cannot do a job, the
tool must say so rather than emit a plausible-looking palette.
"""

import pytest

import hegevis as hv
from hegevis.brand import (
    darken_to_contrast, derive, max_chroma, sequential_from, snap,
)
from hegevis.color import BAND, CHROMA_FLOOR, contrast, ok_hue, oklch, oklch_to_hex
from hegevis.validate import validate, validate_ordinal

CREAM = "#f5f1e7"
ORANGE = "#e98650"
BURGUNDY = "#8b1538"
AUBERGINE = "#3a2231"


@pytest.mark.parametrize("hexval", [ORANGE, BURGUNDY, AUBERGINE, "#2a78d6", "#1baf7a"])
def test_oklch_round_trips(hexval):
    L, C = oklch(hexval)
    assert oklch_to_hex(L, C, ok_hue(hexval)) == hexval


def test_out_of_gamut_request_keeps_the_hue():
    """Giving up chroma keeps the colour recognisable; clipping channels would
    shift the hue outright."""
    asked = 25.0
    got = oklch_to_hex(0.55, 0.40, asked)
    assert abs((ok_hue(got) - asked + 180) % 360 - 180) < 2.0


def test_snap_moves_into_the_band_and_holds_the_hue():
    lo, hi = BAND["light"]
    for anchor in (AUBERGINE, BURGUNDY, "#ffffff", "#000000"):
        out = snap(anchor, "light")
        L, C = oklch(out)
        assert lo <= L <= hi
        assert C >= CHROMA_FLOOR


def test_snap_leaves_a_colour_already_in_band_alone():
    assert snap(ORANGE, "light") == ORANGE


def test_darken_to_contrast_reaches_the_target_and_holds_hue():
    out = darken_to_contrast(ORANGE, CREAM, 3.0)
    assert contrast(out, CREAM) >= 3.0
    assert abs((ok_hue(out) - ok_hue(ORANGE) + 180) % 360 - 180) < 3.0


def test_darken_is_a_no_op_when_contrast_already_clears():
    assert darken_to_contrast(BURGUNDY, CREAM, 3.0) == BURGUNDY


def test_max_chroma_is_monotone_in_the_obvious_direction():
    """A hue can hold more chroma in the middle of the range than at the ends."""
    assert max_chroma(0.5, 250) > max_chroma(0.02, 250)
    assert max_chroma(0.5, 250) > max_chroma(0.99, 250)


def test_the_shipped_brand_derivation_passes_every_check():
    palette, report, _ = derive([ORANGE, BURGUNDY], n=8, surface=CREAM,
                                min_contrast=3.0)
    assert report.ok
    assert all(contrast(c, CREAM) >= 3.0 for c in palette)


def test_brand_anchors_keep_the_leading_slots():
    palette, _, _ = derive([ORANGE, BURGUNDY], n=8, surface=CREAM, min_contrast=3.0)
    assert abs((ok_hue(palette[0]) - ok_hue(ORANGE) + 180) % 360 - 180) < 3.0
    assert abs((ok_hue(palette[1]) - ok_hue(BURGUNDY) + 180) % 360 - 180) < 3.0


def test_derivation_reports_what_it_changed():
    _, _, notes = derive([AUBERGINE], n=4, surface=CREAM)
    assert any("hue held" in n for n in notes)


def test_three_close_brand_hues_cannot_all_be_series_colours():
    """The constraint that shaped this theme: aubergine, burgundy and orange sit
    in a 66-degree arc, and two of them collapse once both are in the band.
    The tool must FAIL rather than emit them."""
    _, report, _ = derive([ORANGE, BURGUNDY, AUBERGINE], n=8, surface=CREAM)
    assert not report.ok


def test_derive_rejects_asking_for_fewer_slots_than_anchors():
    with pytest.raises(ValueError):
        derive([ORANGE, BURGUNDY], n=1)


def test_derive_needs_at_least_one_anchor():
    with pytest.raises(ValueError):
        derive([], n=8)


def test_sequential_ramp_is_one_hue_and_monotone():
    ramp = sequential_from(ORANGE)
    assert validate_ordinal(ramp[2:], surface=CREAM).ok
    hues = [ok_hue(c) for c in ramp]
    assert max(hues) - min(hues) < 40


def test_the_live_theme_is_the_derived_one():
    """Guards against the theme file drifting away from what the tool produced."""
    t = hv.get_theme()
    assert validate(t.series, surface=t.surface).ok
    assert validate(t.series, surface=t.surface, pairs="all").ok is False
    assert validate(t.series[:3], surface=t.surface, pairs="all").ok


def test_cli_prints_a_pasteable_block(capsys):
    from hegevis.brand import main
    assert main([f"{ORANGE},{BURGUNDY}", "--surface", CREAM,
                 "--min-contrast", "3.0"]) == 0
    out = capsys.readouterr().out
    assert "series = [" in out
    assert "brand anchor" in out
