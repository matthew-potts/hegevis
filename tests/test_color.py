"""The colour maths is a twin of the reference JS validator -- these are the
values that implementation produces, so a drift shows up here first."""

import math

import pytest

from hegevis import color as c


def test_contrast_matches_reference():
    assert c.contrast("#2a78d6", "#fcfcfb") == pytest.approx(4.301, abs=1e-3)
    assert c.contrast("#ffffff", "#000000") == pytest.approx(21.0, abs=1e-6)


def test_oklch_matches_reference():
    L, C = c.oklch("#2a78d6")
    assert L == pytest.approx(0.5753, abs=1e-4)
    assert C == pytest.approx(0.1626, abs=1e-4)


def test_delta_e_matches_reference():
    # The worst adjacent pair of the shipped order, per the JS validator.
    d = min(c.delta_e("#eda100", "#1baf7a", "protan"),
            c.delta_e("#eda100", "#1baf7a", "deutan"))
    assert d == pytest.approx(9.1, abs=0.05)
    assert c.delta_e("#e87ba4", "#eda100") == pytest.approx(19.6, abs=0.05)


def test_gray_has_no_chroma():
    assert c.oklch("#888888")[1] == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize("raw", [
    " #2a78d6 ", " #2a78d6", "#2a78d6　", " #2a78d6 ",
    " #2a78d6", "#2a78d6 ", " #2a78d6 ", " #2a78d6",
])
def test_strips_the_whitespace_pasting_introduces(raw):
    assert c.strip_ws(raw) == "#2a78d6"
    assert c.is_hex_color(c.strip_ws(raw))


def test_bad_hex_raises_rather_than_failing_open():
    # Unguarded, a bad hex propagates NaN and every check silently passes.
    with pytest.raises(c.BadColor):
        c.oklch("#nothex")
    with pytest.raises(c.BadColor):
        c.contrast("blue", "#ffffff")


def test_simulation_changes_colour_but_stays_in_gamut():
    for kind in ("protan", "deutan", "tritan"):
        rgb = c.simulate("#eb6834", kind)
        assert all(0.0 <= v <= 1.0 for v in rgb)
    assert c.simulate_hex("#eb6834", "deutan") != "#eb6834"
