"""The six checks. If the brand palette is swapped in and these fail, that is
the package doing its job -- do not relax the thresholds to make them pass."""

import pytest

import hegevis as hv
from hegevis.validate import FAIL, PASS, WARN


def states(report):
    return {c.name: c.state for c in report.checks}


def test_shipped_palette_passes_adjacent_in_light():
    t = hv.get_theme()
    rep = hv.validate(t.series, mode="light", surface=t.surface)
    assert rep.ok
    s = states(rep)
    assert s["Lightness band"] == PASS
    assert s["Chroma floor"] == PASS
    assert s["CVD separation"] == PASS
    assert s["Normal-vision floor"] == PASS


def test_eight_slots_cannot_pass_all_pairs():
    """A documented property: all-pairs forms cap the series count, and no
    reordering fixes it. Guards against someone 'fixing' it by reordering."""
    t = hv.get_theme()
    rep = hv.validate(t.series, mode="light", surface=t.surface, pairs="all")
    assert not rep.ok


def test_first_three_slots_pass_all_pairs():
    t = hv.get_theme()
    rep = hv.validate(t.series[:3], mode="light", surface=t.surface, pairs="all")
    assert rep.ok


def test_near_duplicate_colours_fail_both_separation_gates():
    rep = hv.validate(["#2a78d6", "#2b79d7"])
    assert not rep.ok
    s = states(rep)
    assert s["CVD separation"] == FAIL
    assert s["Normal-vision floor"] == FAIL


def test_gray_fails_the_chroma_floor():
    rep = hv.validate(["#2a78d6", "#888888"])
    assert states(rep)["Chroma floor"] == FAIL


def test_low_contrast_warns_but_does_not_fail():
    """Sub-3:1 is a documented relief case, not a hard failure -- it obliges
    visible labels instead."""
    rep = hv.validate(["#eda100", "#2a78d6"])
    assert states(rep)["Contrast vs surface"] == WARN
    assert rep.ok


@pytest.mark.parametrize("n", [2, 3, 4, 5])
def test_ordinal_steps_the_package_hands_out_always_validate(n):
    """Palette.ordinal() drops steps too pale to read as a mark, so whatever it
    returns must clear the ordinal checks."""
    t = hv.get_theme()
    steps = hv.Palette(t).ordinal(n)
    rep = hv.validate_ordinal(steps, surface=t.surface)
    assert rep.ok, rep


def test_full_ramp_is_paler_than_the_ordinal_floor_by_design():
    """The lightest step of a *sequential* ramp may recede toward the surface;
    that is what makes 'near zero' read as near zero on a heatmap."""
    t = hv.get_theme()
    assert not hv.validate_ordinal(t.sequential, surface=t.surface).ok
    assert hv.contrast(t.sequential[0], t.surface) < 2.0


def test_categorical_checks_reject_a_ramp_by_design():
    t = hv.get_theme()
    assert not hv.validate(t.sequential, surface=t.surface).ok


def test_out_of_order_ramp_fails_monotonicity():
    rep = hv.validate_ordinal(["#256abf", "#cde2fb", "#0d366b"])
    assert states(rep)["Lightness monotone"] == FAIL


def test_raise_for_status():
    with pytest.raises(hv.PaletteError):
        hv.validate(["#2a78d6", "#2b79d7"]).raise_for_status()


def test_cli_exit_codes():
    from hegevis.validate import main
    assert main(["#2a78d6,#eb6834,#1baf7a"]) == 0
    assert main(["#2a78d6,#2b79d7"]) == 1
    assert main(["not-a-hex"]) == 2
