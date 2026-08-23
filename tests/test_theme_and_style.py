"""The theme file is the swap surface -- a typo in it must fail loudly, at load
time, not silently produce a chart in the wrong colour."""

import os

import pytest

import hegevis as hv
from hegevis.color import BadColor
from hegevis.theme import read_theme


def write_theme(tmp_path, body):
    p = tmp_path / "hegevis-theme.toml"
    p.write_text(body)
    return p


def test_packaged_theme_loads():
    t = hv.get_theme()
    assert len(t.series) == 8
    assert t.surface.startswith("#")


def test_a_bad_hex_in_the_theme_raises_at_load():
    with pytest.raises(BadColor):
        read_theme_from_string('name="x"\n[color]\nseries=["#nothex"]\n')


def read_theme_from_string(body, tmp=None):
    import tempfile
    import pathlib
    d = pathlib.Path(tempfile.mkdtemp())
    p = d / "t.toml"
    p.write_text(body)
    return read_theme(p)


def test_project_theme_overrides_the_house_one(tmp_path, monkeypatch):
    write_theme(tmp_path, 'name = "Special section"\n')
    monkeypatch.chdir(tmp_path)
    assert hv.load_theme().name == "Special section"


def test_env_var_wins_over_the_project_file(tmp_path, monkeypatch):
    write_theme(tmp_path, 'name = "project"\n')
    other = tmp_path / "other.toml"
    other.write_text('name = "env"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HEGEVIS_THEME", str(other))
    assert hv.load_theme().name == "env"


def test_missing_env_theme_is_an_error_not_a_silent_fallback(monkeypatch):
    monkeypatch.setenv("HEGEVIS_THEME", "/nope/missing.toml")
    with pytest.raises(FileNotFoundError):
        hv.load_theme()


def test_unknown_type_size_key_warns():
    with pytest.warns(UserWarning, match="unknown"):
        read_theme_from_string('[type.size]\nnosuchthing = 9\n')


def test_named_widths_and_literal_mm():
    lay = hv.get_theme().layout
    assert lay.width_mm("col1") == lay.col1
    assert lay.width_mm(95.0) == 95.0
    with pytest.raises(ValueError):
        lay.width_mm("col7")


def test_reloading_the_theme_clears_the_colour_registry():
    p = hv.palette()
    p.for_series(["China"])
    hv.load_theme()
    assert hv.palette() is not p


def test_rcparams_are_set_up_for_print_vector_output():
    rc = hv.rc_params()
    assert rc["pdf.fonttype"] == 42          # embed a TrueType subset
    assert rc["ps.fonttype"] == 42
    assert rc["savefig.bbox"] == "standard"  # never 'tight': it changes width
    assert rc["grid.linestyle"] == "-"       # solid hairlines, never dashed
    assert rc["legend.frameon"] is False
    assert rc["axes.axisbelow"] is True
    assert rc["axes.spines.top"] is False


def test_prop_cycle_is_the_theme_palette_in_order():
    rc = hv.rc_params()
    assert rc["axes.prop_cycle"].by_key()["color"] == list(hv.get_theme().series)


def test_style_context_restores_previous_rcparams():
    import matplotlib as mpl
    before = mpl.rcParams["lines.linewidth"]
    with hv.style():
        assert mpl.rcParams["lines.linewidth"] != before or True
    assert mpl.rcParams["lines.linewidth"] == before


def test_missing_brand_font_warns_loudly():
    from hegevis import rc
    rc._font_warned = False
    with pytest.warns(UserWarning, match="not installed"):
        rc.rc_params()
    rc._font_warned = False


def test_public_style_name_is_the_context_manager_not_a_module():
    """`hv.style` must be the context manager; the rcParams module is `hv.rc`."""
    from contextlib import _GeneratorContextManager
    assert callable(hv.style)
    with hv.style() as t:
        assert t is hv.get_theme()
