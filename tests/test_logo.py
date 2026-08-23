"""The masthead mark. The point of these tests is that it is NOT optional:
whichever way a chart reaches the page, it leaves with the logo on it."""

import re

import matplotlib.pyplot as plt
import numpy as np
import pytest

import hegevis as hv
from hegevis import logo as hvlogo


def logo_axes(fig):
    return [ax for ax in fig.axes if hvlogo.is_logo_axes(ax)]


# A theme file needs at least one series colour to be usable at all; these
# tests are about [logo], so the rest is the minimum that lets a figure build.
def write_theme(path, body: str) -> None:
    path.write_text('name = "test"\n[color]\nseries = ["#d1703a"]\n' + body)


# -- it is furniture, not a parameter -----------------------------------------

def test_every_figure_from_the_package_carries_the_mark():
    fig, ax = hv.figure("col1")
    assert len(logo_axes(fig)) == 1


def test_a_finished_figure_carries_the_mark():
    fig, ax = hv.figure("col2")
    ax.plot([1, 2, 3])
    hv.finish(fig, title="Marked", source="Somewhere")
    assert len(logo_axes(fig)) == 1


def test_a_figure_grid_carries_exactly_one_mark():
    fig, axes = hv.figure("col2", nrows=2, ncols=2)
    hv.finish(fig, title="Panels")
    assert len(logo_axes(fig)) == 1


def test_save_stamps_a_figure_that_never_went_through_the_house_helpers(tmp_path):
    """The escape hatch is closed: a bare plt.subplots() saved through the
    package still leaves with the mark."""
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([1, 2, 3])
    assert not logo_axes(fig)
    hv.save(fig, tmp_path / "bare.pdf")
    assert len(logo_axes(fig)) == 1


def test_stamping_is_idempotent_however_many_times_it_is_asserted():
    fig, ax = hv.figure("col1")
    hv.finish(fig, title="Once")
    hv.stamp_logo(fig)
    hv.stamp_logo(fig)
    assert len(logo_axes(fig)) == 1


def test_the_mark_survives_a_round_trip_to_pdf_and_svg(tmp_path):
    fig, ax = hv.figure("col1")
    ax.plot([1, 2, 3])
    hv.finish(fig, title="Both")
    for name in ("out.pdf", "out.svg"):
        hv.save(fig, tmp_path / name)
    assert b"/Subtype /Image" in (tmp_path / "out.pdf").read_bytes()
    assert b"image" in (tmp_path / "out.svg").read_bytes()


# -- where it sits -------------------------------------------------------------

def test_the_mark_hangs_off_the_right_margin_at_the_foot():
    t = hv.get_theme()
    fig, ax = hv.figure("col2")
    w_in, h_in = fig.get_size_inches()
    box = logo_axes(fig)[0].get_position()

    right_mm = (1 - box.x1) * w_in * 25.4
    bottom_mm = box.y0 * h_in * 25.4
    assert right_mm == pytest.approx(t.layout.margin.right, abs=0.01)
    assert bottom_mm == pytest.approx(t.logo.inset_mm, abs=0.01)


def test_the_mark_is_the_same_physical_size_on_every_column_width():
    """Sized in millimetres, not as a fraction -- so it is one mark across the
    publication rather than a big one on page-width charts."""
    sizes = []
    for name in ("col1", "col2"):
        fig, ax = hv.figure(name)
        w_in, h_in = fig.get_size_inches()
        box = logo_axes(fig)[0].get_position()
        sizes.append((box.width * w_in, box.height * h_in))
    assert sizes[0] == pytest.approx(sizes[1], abs=1e-9)


def test_the_mark_keeps_the_artwork_aspect_ratio():
    fig, ax = hv.figure("col1")
    w_in, h_in = fig.get_size_inches()
    box = logo_axes(fig)[0].get_position()
    px_h, px_w = hvlogo.image().shape[:2]
    assert (box.width * w_in) / (box.height * h_in) == pytest.approx(px_w / px_h)


def test_the_theme_sets_the_height():
    t = hv.get_theme()
    hv.set_theme(hv.Theme(**{**t.__dict__, "logo": hv.Logo(height_mm=12.0)}))
    fig, ax = hv.figure("col1")
    h_mm = logo_axes(fig)[0].get_position().height * fig.get_size_inches()[1] * 25.4
    assert h_mm == pytest.approx(12.0)


# -- it does not collide with anything ----------------------------------------

def test_the_plot_area_clears_the_mark():
    fig, ax = hv.figure("col1")
    h_in = fig.get_size_inches()[1]
    assert ax.get_position().y0 * h_in >= logo_axes(fig)[0].get_position().y1 * h_in


def test_a_thin_bottom_margin_still_leaves_room_for_the_mark():
    """The reservation is a floor, so a theme with a tight foot cannot end up
    drawing the plot over the logo."""
    t = hv.get_theme()
    layout = hv.theme.Layout(**{**t.layout.__dict__,
                                "margin": hv.theme.Margin(bottom=3.0)})
    hv.set_theme(hv.Theme(**{**t.__dict__, "layout": layout}))
    fig, ax = hv.figure("col1")
    h_in = fig.get_size_inches()[1]
    assert ax.get_position().y0 * h_in >= logo_axes(fig)[0].get_position().y1 * h_in


def test_a_long_source_line_wraps_clear_of_the_mark():
    fig, ax = hv.figure("col1")
    ax.plot([1, 2, 3])
    hv.finish(fig, title="Crowded footer",
              source="A citation long enough that it would otherwise run the "
                     "full measure and straight underneath the masthead mark",
              note="And a note that is also much longer than one line of a "
                   "narrow single column measure could ever hold")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    mark = logo_axes(fig)[0].get_window_extent(renderer=renderer)
    for text in fig.texts:
        assert not mark.overlaps(text.get_window_extent(renderer=renderer))


def test_the_title_still_uses_the_full_measure():
    """Only the footer shares a band with the mark; narrowing the title too
    would cost a line at the top of every chart for nothing."""
    fig, ax = hv.figure("col1")
    hv.finish(fig, title="A headline long enough that it cannot possibly fit on "
                         "a single line of a narrow single column measure")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    w_in, _ = fig.get_size_inches()
    m = hv.get_theme().layout.margin
    full_px = (w_in - (m.left + m.right) / 25.4) * fig.dpi
    widest = max(t.get_window_extent(renderer=renderer).width for t in fig.texts)
    # It used more than the footer's shortened measure would have allowed.
    assert widest > full_px - hvlogo.size_in()[0] * fig.dpi


# -- it stays out of the colour machinery --------------------------------------

def test_the_mark_is_not_counted_as_a_chart_colour():
    """The logo's sand and orange are placed artwork, not data ink -- letting
    them into the manifest would have prepress chasing UNDECLARED brand inks."""
    fig, ax = hv.figure("col1")
    hv.line(ax, {"a": [1, 2]}, x=[0, 1])
    used = hv.colors_used(fig)
    assert "#f7d687" not in used and "#ee8d5a" not in used


def test_a_cvd_proof_leaves_the_mark_alone():
    fig, ax = hv.figure("col1")
    hv.line(ax, {"a": [1, 2], "b": [2, 1]}, x=[0, 1])
    before = hvlogo.image().copy()
    hv.simulate_figure(fig, "deutan")
    assert np.array_equal(logo_axes(fig)[0].images[0].get_array(), before)


# -- the artwork itself ---------------------------------------------------------

def test_the_packaged_artwork_is_transparent_where_it_is_not_the_mark():
    """A JPEG's white field would print as a pale square on the cover cream."""
    img = hvlogo.image()
    assert img.shape[2] == 4
    assert img[0, 0, 3] == 0 and img[-1, -1, 3] == 0
    assert img[..., 3].max() == pytest.approx(1.0)


def test_the_pdf_carries_the_artwork_at_full_resolution(tmp_path):
    """interpolation='none' is load-bearing: any other setting has matplotlib
    resample the mark to screen resolution on the way into the PDF."""
    fig, ax = hv.figure("col1")
    hv.finish(fig, title="Press ready")
    out = tmp_path / "press.pdf"
    hv.save(fig, out)
    px_h, px_w = hvlogo.image().shape[:2]
    found = re.findall(rb"/Width (\d+)\s*/Height (\d+)", out.read_bytes())
    assert (str(px_w).encode(), str(px_h).encode()) in found


# -- overriding it --------------------------------------------------------------

def test_a_theme_can_point_at_its_own_artwork(tmp_path):
    from PIL import Image

    Image.new("RGBA", (40, 20), (1, 2, 3, 255)).save(tmp_path / "section.png")
    write_theme(tmp_path / "hegevis-theme.toml", '[logo]\npath = "section.png"\n')
    hv.load_theme(tmp_path / "hegevis-theme.toml")
    assert hvlogo.resolve_path() == tmp_path / "section.png"

    fig, ax = hv.figure("col1")
    w_in, h_in = fig.get_size_inches()
    box = logo_axes(fig)[0].get_position()
    assert (box.width * w_in) / (box.height * h_in) == pytest.approx(2.0)


def test_a_theme_naming_artwork_that_is_not_there_fails_loudly(tmp_path):
    write_theme(tmp_path / "hegevis-theme.toml", '[logo]\npath = "nope.png"\n')
    hv.load_theme(tmp_path / "hegevis-theme.toml")
    with pytest.raises(hv.MissingLogo, match="not something the package can skip"):
        hv.figure("col1")
