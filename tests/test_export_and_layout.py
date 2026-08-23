"""Output. The publication's requirement is print vector with the type
embedded, at exactly the column width the figure was built for."""

import pytest

import hegevis as hv


def test_figure_is_built_at_the_real_column_width():
    t = hv.get_theme()
    fig, ax = hv.figure("col2")
    w_mm = fig.get_size_inches()[0] * 25.4
    assert w_mm == pytest.approx(t.layout.col2)


def test_literal_width_in_mm_is_honoured():
    fig, ax = hv.figure(95.0, height=60.0)
    w, h = (v * 25.4 for v in fig.get_size_inches())
    assert (w, h) == pytest.approx((95.0, 60.0))


def test_figure_grid_returns_an_axes_array():
    fig, axes = hv.figure("col2", nrows=2, ncols=2)
    assert axes.shape == (2, 2)


def test_finish_wraps_a_long_title_by_measuring_the_face():
    fig, ax = hv.figure("col1")
    ax.plot([1, 2, 3])
    hv.finish(fig, title="A headline long enough that it cannot possibly fit on "
                         "a single line of a narrow single column measure")
    assert len(fig.texts) >= 2  # it wrapped


def test_finish_pushes_the_plot_down_for_a_taller_title():
    fig1, ax1 = hv.figure("col1")
    hv.finish(fig1, title="Short")
    top1 = ax1.get_position().y1

    fig2, ax2 = hv.figure("col1")
    hv.finish(fig2, title="A headline long enough that it cannot possibly fit "
                          "on one line of a narrow single column measure at all")
    assert ax2.get_position().y1 < top1


def test_source_line_is_prefixed_and_placed_in_the_footer():
    fig, ax = hv.figure("col1")
    hv.finish(fig, source="IMF DOTS", note="Provisional.")
    texts = [t.get_text() for t in fig.texts]
    assert "Source: IMF DOTS" in texts
    assert "Provisional." in texts


def test_save_writes_a_pdf_with_embedded_type(tmp_path):
    fig, ax = hv.figure("col1")
    ax.plot([1, 2, 3])
    hv.finish(fig, title="Embedded")
    out = tmp_path / "chart.pdf"
    hv.save(fig, out)
    blob = out.read_bytes()
    assert blob.startswith(b"%PDF")
    assert b"/FontFile" in blob  # the whole point of pdf.fonttype 42


def test_save_defaults_to_pdf_when_no_suffix_is_given(tmp_path):
    fig, ax = hv.figure("col1")
    written = hv.save(fig, tmp_path / "chart")
    assert written[0].suffix == ".pdf"
    assert written[0].exists()


def test_save_refuses_tight_bbox_because_it_changes_the_width(tmp_path):
    fig, ax = hv.figure("col1")
    with pytest.warns(UserWarning, match="column width"):
        hv.save(fig, tmp_path / "c.pdf", bbox_inches="tight")
    # and the file still comes out at the requested width
    assert fig.get_size_inches()[0] * 25.4 == pytest.approx(hv.get_theme().layout.col1)


def test_save_warns_when_asked_for_a_raster(tmp_path):
    fig, ax = hv.figure("col1")
    with pytest.warns(UserWarning, match="raster"):
        hv.save(fig, tmp_path / "c.png")


def test_svg_can_keep_text_live_or_outline_it(tmp_path):
    fig, ax = hv.figure("col1")
    ax.plot([1, 2, 3])
    hv.finish(fig, title="Outlines")

    live = tmp_path / "live.svg"
    hv.save(fig, live)
    assert b"<text" in live.read_bytes()

    outlined = tmp_path / "outlined.svg"
    hv.save(fig, outlined, outline_text=True)
    assert b"<text" not in outlined.read_bytes()


def test_colors_used_walks_the_artists():
    t = hv.get_theme()
    fig, ax = hv.figure("col1")
    hv.line(ax, {"a": [1, 2], "b": [2, 1]}, x=[0, 1])
    used = hv.colors_used(fig)
    assert t.series[0].lower() in used
    assert t.series[1].lower() in used


def test_manifest_flags_colours_with_no_declared_cmyk(tmp_path):
    fig, ax = hv.figure("col1")
    hv.line(ax, {"a": [1, 2]}, x=[0, 1])
    written = hv.save(fig, tmp_path / "c.pdf", manifest=True)
    text = written[1].read_text()
    assert "UNDECLARED" in text
    assert hv.get_theme().series[0].lower() in text


def test_manifest_uses_declared_builds_when_the_theme_has_them():
    t = hv.get_theme()
    themed = hv.Theme(**{**t.__dict__, "cmyk": {t.series[0].lower(): (80, 47, 0, 0)}})
    hv.set_theme(themed)
    fig, ax = hv.figure("col1")
    hv.line(ax, {"a": [1, 2]}, x=[0, 1])
    text = hv.cmyk_manifest(fig)
    assert "C 80 M 47" in text


def test_simulate_figure_recolours_for_a_cvd_proof():
    fig, ax = hv.figure("col1")
    hv.line(ax, {"a": [1, 2], "b": [2, 1]}, x=[0, 1])
    before = [ln.get_color() for ln in ax.get_lines()]
    hv.simulate_figure(fig, "deutan")
    after = [ln.get_color() for ln in ax.get_lines()]
    assert before != after


def test_output_is_print_correct_even_if_rcparams_were_reset(tmp_path):
    """Regression: font embedding must not depend on the script having called
    use() -- save() pins the output params itself."""
    import matplotlib as mpl

    fig, ax = hv.figure("col1")
    ax.plot([1, 2, 3])
    hv.finish(fig, title="Reset")
    mpl.rcdefaults()  # a stray rcdefaults() anywhere in the analyst's script
    out = tmp_path / "chart.pdf"
    hv.save(fig, out)
    assert b"/FontFile" in out.read_bytes()


def test_a_hegevis_figure_is_styled_without_calling_use():
    import matplotlib as mpl

    mpl.rcdefaults()
    t = hv.get_theme()
    fig, ax = hv.figure("col1")
    assert mpl.rcParams["figure.facecolor"] == t.surface
    assert mpl.rcParams["axes.prop_cycle"].by_key()["color"] == list(t.series)
