"""The v2 house look: a box, an off-white ground, a masthead tab, one text
size inside the plot, and text short enough to read at a glance."""

import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import pytest

import hegevis as hv
from hegevis import layout as hvlayout


def tabs(fig):
    return [a for a in fig.artists if a is getattr(fig, "_hegevis_tab", None)]


# -- the box -------------------------------------------------------------------

def test_a_chart_is_a_box_taller_than_it_is_wide():
    fig, ax = hv.figure("col1")
    w, h = fig.get_size_inches()
    assert h > w
    assert h / w == pytest.approx(hv.get_theme().layout.default_ratio)


def test_the_off_white_ground_fills_the_whole_box():
    """Nothing in the house style is drawn on white -- not the figure, and not
    the plot area, which would otherwise show as a paler rectangle inside it."""
    t = hv.get_theme()
    fig, ax = hv.figure("col1")
    assert fig.get_facecolor() == plt.matplotlib.colors.to_rgba(t.surface)
    assert ax.get_facecolor() == plt.matplotlib.colors.to_rgba(t.surface)


def test_the_ground_is_off_white_not_white():
    t = hv.get_theme()
    assert t.surface.lower() != "#ffffff"
    r, g, b = (int(t.surface[i:i + 2], 16) for i in (1, 3, 5))
    assert max(r, g, b) < 250          # genuinely off the paper
    assert max(r, g, b) - min(r, g, b) > 4  # and warm, not a neutral grey


def test_the_saved_file_carries_the_ground(tmp_path):
    t = hv.get_theme()
    fig, ax = hv.figure("col1")
    hv.finish(fig, title="Ground")
    out = tmp_path / "c.svg"
    hv.save(fig, out)
    assert t.surface.lower().encode() in out.read_bytes().lower()


# -- the masthead tab ----------------------------------------------------------

def test_every_figure_opens_with_the_masthead_tab():
    fig, ax = hv.figure("col1")
    assert len(tabs(fig)) == 1


def test_the_tab_is_brand_orange_not_a_borrowed_red():
    """The layout is the convention; the colour is ours."""
    t = hv.get_theme()
    fig, ax = hv.figure("col1")
    assert fig._hegevis_tab.get_facecolor() == plt.matplotlib.colors.to_rgba(t.tab.color)
    assert t.tab.color.lower() == t.series[0].lower()


def test_the_tab_sits_top_left_above_the_title():
    t = hv.get_theme()
    fig, ax = hv.figure("col1")
    hv.finish(fig, title="Under the tab")
    w_in, h_in = fig.get_size_inches()
    box = fig._hegevis_tab.get_window_extent()
    left_mm = box.x0 / fig.dpi * 25.4
    assert left_mm == pytest.approx(t.layout.margin.left, abs=0.1)
    # every title line starts below the tab
    tab_bottom = box.y0
    assert all(txt.get_window_extent().y1 <= tab_bottom + 1 for txt in fig.texts)


def test_stamping_the_tab_twice_leaves_one():
    fig, ax = hv.figure("col1")
    hv.finish(fig, title="Once")
    hvlayout._tab(fig, hv.get_theme())
    assert len(tabs(fig)) == 1


# -- one text size -------------------------------------------------------------

def test_everything_inside_the_plot_is_one_size():
    """Five slightly different sizes is not a hierarchy a reader can decode at
    88mm; it just looks busy."""
    t = hv.get_theme()
    assert t.size.axis == t.size.tick == t.size.label == t.size.legend == t.size.body


def test_the_footnote_is_much_smaller_than_the_body():
    t = hv.get_theme()
    assert t.size.footnote < t.size.body
    assert t.size.footnote / t.size.body <= 0.85
    assert t.size.source == t.size.footnote


def test_the_source_line_is_actually_set_at_the_footnote_size():
    t = hv.get_theme()
    fig, ax = hv.figure("col1")
    hv.finish(fig, title="Small print", source="Somewhere")
    sizes = {round(x.get_fontsize(), 2) for x in fig.texts
             if x.get_text().startswith("Source:")}
    assert sizes == {round(t.size.footnote, 2)}


def test_a_theme_naming_the_retired_per_role_sizes_says_so(tmp_path):
    p = tmp_path / "hegevis-theme.toml"
    p.write_text('name = "old"\n[color]\nseries = ["#d1703a"]\n'
                 '[type.size]\ntick = 9.0\n')
    with pytest.warns(UserWarning, match="no longer exist"):
        hv.load_theme(p)


# -- the two licensed faces, in their two roles --------------------------------

def test_both_house_faces_are_registered_from_the_local_directory():
    from hegevis import fonts
    fonts.register()
    have = fonts.installed()
    if not (Path(fonts.FONT_DIR).is_dir() and fonts.font_files()):
        pytest.skip("licensed faces are not present on this machine")
    assert "Gill Sans" in have
    assert "Tiempos Headline" in have


def test_the_title_takes_the_display_face_and_the_subtitle_does_not():
    """Both faces are used, in the roles the publication uses them for: the
    serif sets the headline, the sans sets the running gloss below it."""
    t = hv.get_theme()
    if "Tiempos Headline" not in __import__("hegevis").fonts.installed():
        pytest.skip("licensed faces are not present on this machine")
    fig, ax = hv.figure("col1")
    hv.finish(fig, title="Headline", subtitle="A running gloss")
    by_text = {x.get_text(): x for x in fig.texts}
    assert by_text["Headline"].get_fontfamily()[0] == "Tiempos Headline"
    assert by_text["A running gloss"].get_fontfamily()[0] != "Tiempos Headline"


def test_the_title_falls_back_to_the_chart_sans_not_to_dejavu():
    """An unlicensed machine should degrade to the house sans, not to
    matplotlib's default face."""
    t = hv.get_theme()
    fig, ax = hv.figure("col1")
    hv.finish(fig, title="Headline")
    fam = [x for x in fig.texts if x.get_text() == "Headline"][0].get_fontfamily()
    assert list(t.family)[0] in fam


# -- word limits ---------------------------------------------------------------

def test_an_overlong_title_warns_rather_than_shipping_quietly():
    fig, ax = hv.figure("col1")
    with pytest.warns(UserWarning, match="over the house limit"):
        hv.finish(fig, title=" ".join(["word"] * 30))


def test_an_overlong_footnote_warns():
    fig, ax = hv.figure("col1")
    with pytest.warns(UserWarning, match="footnote is"):
        hv.finish(fig, source=" ".join(["word"] * 40))


def test_a_title_inside_the_limit_is_silent():
    fig, ax = hv.figure("col1")
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        hv.finish(fig, title="Goods exports diverge",
                  subtitle="Merchandise exports, 2015 = 100",
                  source="IMF DOTS")


def test_the_warning_never_truncates_the_analyst_s_words():
    """Cutting someone's title silently would be worse than shipping a long one."""
    long = " ".join(["word"] * 30)
    fig, ax = hv.figure("col1")
    with pytest.warns(UserWarning):
        hv.finish(fig, title=long)
    shown = " ".join(t.get_text() for t in fig.texts)
    assert shown.count("word") == 30


# -- the value scale on the right ----------------------------------------------

def test_the_value_scale_is_labelled_on_the_right(frame_free_line):
    ax = frame_free_line
    assert not any(lbl.get_visible() for lbl in ax.get_yticklabels(which="major")
                   if lbl.get_position()[0] == 0)


@pytest.fixture
def frame_free_line():
    fig, ax = hv.figure("col1")
    hv.line(ax, {"a": [1, 2, 3]}, x=[0, 1, 2])
    return ax


def test_ranked_keeps_its_category_names_on_the_left():
    """Names are not a scale: they read as the row's own label only beside the
    bar's origin, whatever side the value scale is on."""
    fig, ax = hv.figure("col1")
    hv.ranked(ax, ["alpha", "beta"], [2, 1])
    assert ax.yaxis.get_tick_params()["labelleft"]
    assert not ax.yaxis.get_tick_params()["labelright"]
