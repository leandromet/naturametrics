"""report_kit — the shared PDF/HTML report kit (doc/14 §2.10).

Canonical tests; offline (no Earth Engine). Rasters are synthesised with
Pillow, so what is tested is the kit's layout and image rules, not any data.
"""

import ast
import base64
import io
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("reportlab")
PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from naturametrics import report_kit as rk  # noqa: E402
from naturametrics.report_kit import images, maps, style  # noqa: E402
from naturametrics.report_kit.browser_capture import JobStore, build_capture_script  # noqa: E402
from naturametrics.report_kit.text import fmt_num, fmt_pct, inline_markup, t  # noqa: E402

KIT = Path(rk.__file__).resolve().parent


def _png(w, h, mode="RGB", noisy=False):
    img = Image.new(mode, (w, h), (30, 120, 60) if mode == "RGB" else (30, 120, 60, 255))
    if noisy:
        px = img.load()
        for y in range(0, h, 3):
            for x in range(0, w, 3):
                px[x, y] = ((x * 7) % 255, (y * 5) % 255, (x * y) % 255)
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def _rings():
    import math
    lon, lat = -55.7, -12.5
    return [{"type": "Polygon", "coordinates": [[
        [lon + r / 108 * math.cos(a / 24 * 6.283), lat + r / 111 * math.sin(a / 24 * 6.283)]
        for a in range(25)]]} for r in (1, 5, 10)]


def _report(lang="pt", n_fig=8, n_map=4, png=None, rows=120):
    png = png or _png(1004, 563, noisy=True)
    view = maps.MapView.from_geojson(_rings())
    comp = rk.MapComposition(view=view, backdrop=_png(1400, 900, noisy=True),
                             overlays=[_png(1004, 650, "RGBA")],
                             vectors=[rk.VectorLayer(r, dash=(3, 2)) for r in _rings()],
                             clip_to=_rings()[-1],
                             legend=[rk.LegendItem("#1f8d49", "Floresta")],
                             attribution="Contains modified Copernicus Sentinel data 2024")
    meta = rk.ReportMeta(app="Naturametrics", app_url="https://example.org", app_version="0",
                         title="Relatório", subject="Teste · <b>Sujeito</b>", lang=lang)
    blocks = [rk.Callout("Aviso **importante** <script>alert(1)</script>", "disclosure"),
              rk.SideBySide(rk.KeyValues([("a", "b")]),
                            rk.LocatorMap({"type": "Point", "coordinates": [-55.7, -12.5]}, "x")),
              rk.ContentsList([rk.ContentsItem("A"), rk.ContentsItem("B", "not_run", "r")]),
              rk.Paragraph("Texto **negrito** e *itálico*.", lead=True),
              rk.Figure("missing", "sem imagem", unavailable_reason="motivo"),
              rk.Table(["Classe", "ha"], [[f"c{i}", i * 1.5] for i in range(rows)], "tabela",
                       align=["l", "r"], max_rows=rows),
              rk.ProvenanceTable([{"name": "n", "dataset_id": "d", "bands": ["b"] * 6,
                                   "scale_m": 30, "reducer": "r", "degraded": True,
                                   "computed_at": "2026-01-01T00:00", "notes": ["x"]}]),
              rk.Citation("cite", ["s"], ["a"]), rk.PageBreak()]
    blocks += [rk.Figure(f"f{i}", f"fig {i}", png=png) for i in range(n_fig)]
    blocks += [rk.MapFigure(comp, f"map {i}") for i in range(n_map)]
    return rk.Report(meta, [rk.Section("S1", blocks, key="s1")])


# --- rendering ------------------------------------------------------------- #

def test_every_block_renders_to_pdf_and_html():
    report = _report()
    pdf = rk.render_pdf(report)
    assert pdf[:5] == b"%PDF-"
    html = rk.render_html(report).decode("utf-8")
    assert html.startswith("<!doctype html>")
    assert "<script>alert(1)</script>" not in html          # escaped, never injected
    assert "&lt;script&gt;" in html
    # links to the app are fine; nothing may be *loaded* from the network
    assert not re.search(r'src="https?://|<link\b', html), "HTML must be self-contained"


def test_size_budget_8_figures_4_maps_3_tables():
    """R9: a typical report stays ≤ 3 MB even from oversized inputs."""
    report = _report(png=_png(4000, 2250, noisy=True))
    report.sections[0].blocks += [rk.Table(["a"], [[i] for i in range(50)], "t2"),
                                  rk.Table(["a"], [[i] for i in range(50)], "t3")]
    pdf = rk.render_pdf(report)
    assert len(pdf) <= 3_000_000, f"{len(pdf) / 1e6:.2f} MB"


def test_oversized_image_is_embedded_at_slot_size():
    big = _png(4000, 2250, noisy=True)
    fitted = images.fit_image(big, style.SLOT_MM["full"], "flat")
    _, w, _ = images.image_size(fitted)
    assert w <= style.slot_px("full") == 1004                    # maps: 150 dpi
    chart = images.fit_image(big, style.SLOT_MM["full"], "flat", dpi=style.CHART_DPI)
    assert images.image_size(chart)[1] <= style.slot_px("full", style.CHART_DPI) == 1472


def test_photo_stays_jpeg_and_flat_stays_png():
    photo = images.fit_image(_png(2000, 1300, noisy=True), 170, "photo")
    assert images.image_size(photo)[0] == "jpeg"
    flat = images.fit_image(_png(800, 400), 170, "flat")
    assert images.image_size(flat)[0] == "png"


def test_long_table_spans_pages_and_repeats_its_header():
    report = _report(n_fig=0, n_map=0, rows=160)
    report.sections[0].blocks[5].max_rows = 160
    pdf = rk.render_pdf(report)
    pages = len(re.findall(rb"/Type /Page\b", pdf))
    assert pages >= 3
    import shutil
    import subprocess
    if shutil.which("pdftotext"):
        text = subprocess.run(["pdftotext", "-", "-"], input=pdf, capture_output=True).stdout
        per_page = text.decode().split("\f")
        with_rows = [p for p in per_page if re.search(r"\bc1\d\d\b", p)]
        assert len(with_rows) >= 2 and all("Classe" in p for p in with_rows)


def test_table_max_rows_notes_the_overflow():
    report = _report(n_fig=0, n_map=0, rows=100)
    report.sections[0].blocks[5].max_rows = 10
    html = rk.render_html(report).decode()
    assert "mais 90 linhas" in html


def test_numbers_are_formatted_for_the_locale_in_tables():
    pt = rk.render_html(_report("pt", 0, 0, rows=3)).decode()
    en = rk.render_html(_report("en", 0, 0, rows=3)).decode()
    assert ">1,5<" in pt and ">1.5<" in en


def test_unavailable_figure_renders_a_placeholder():
    html = rk.render_html(_report(n_fig=0, n_map=0)).decode()
    assert "Figura indisponível — motivo" in html


# --- text ------------------------------------------------------------------ #

@pytest.mark.parametrize("lang,expected", [("pt", "1.234,5"), ("es", "1.234,5"),
                                           ("fr", "1 234,5"), ("en", "1,234.5")])
def test_fmt_num(lang, expected):
    assert fmt_num(1234.5, 1, lang) == expected


def test_fmt_pct_and_missing_values():
    assert fmt_pct(43.4, 1, "pt") == "43,4 %" and fmt_pct(43.4, 1, "en") == "43.4%"
    assert fmt_num(None) == "—" and fmt_num(float("nan")) == "—"


def test_kit_strings_exist_in_all_four_languages():
    from naturametrics.report_kit.text import LANGS, STRINGS
    for key, table in STRINGS.items():
        assert set(LANGS) <= set(table), key
    assert t("page_of", "fr", n=2, total=5) == "page 2 sur 5"


def test_inline_markup_escapes_everything_else():
    assert inline_markup("**a** *b* <i>x</i> & 2*3*4") == \
        "<b>a</b> <i>b</i> &lt;i&gt;x&lt;/i&gt; &amp; 2*3*4"


# --- maps ------------------------------------------------------------------ #

@pytest.mark.parametrize("lat", [0.0, -30.0])
def test_map_view_aspect_and_scale_bar(lat):
    pt = {"type": "Point", "coordinates": [-50.0, lat]}
    view = maps.MapView.from_geojson([pt], min_span_m=10_000)
    assert view.aspect == pytest.approx(style.MAP_ASPECT, rel=1e-6)
    assert view.ground_width_m == pytest.approx(10_000, rel=0.01)
    frac, label = maps.scale_bar(view)
    assert label == "2 km" and frac == pytest.approx(0.2, rel=0.02)


def test_locator_finds_the_uf():
    from naturametrics.report_kit.locator import uf_at
    assert uf_at(-55.7, -12.5) == "MT"
    assert uf_at(-47.9, -15.8) == "DF"
    assert uf_at(-30.0, -40.0) is None


# --- browser capture --------------------------------------------------------- #

def _data_url(png):
    return "data:image/png;base64," + base64.b64encode(png).decode()


def test_jobstore_accepts_valid_and_rejects_foreign_or_bad():
    store = JobStore()
    job = store.create("tok", ["a", "b", "c", "d"])
    assert store.put(job, "a", _data_url(_png(100, 50)), "tok")
    assert not store.put(job, "a", _data_url(_png(100, 50)), "other-token")
    assert not store.put(job, "zzz", _data_url(_png(100, 50)), "tok")
    assert store.put(job, "b", "data:text/html;base64,PGI+", "tok")      # recorded as failure
    assert store.put(job, "c", _data_url(_png(4100, 10)), "tok")         # too wide → failure
    assert store.progress(job) == (3, 4)
    got, errors = store.take(job)
    assert got["a"][:8] == images.PNG_SIG
    assert got["b"] is None and got["c"] is None and got["d"] is None
    assert "timed out" in errors["d"] and "exceeds" in errors["c"]


def test_capture_script_embeds_every_figure_and_callback():
    js = build_capture_script({"k1": {"data": []}, "k2": {"data": []}},
                              {"k1": "(d) => f1(d)", "k2": "(d) => f2(d)"},
                              {"k1": images.chart_opts(), "k2": images.chart_opts("half")})
    assert '"k1":(d) => f1(d)' in js and '"k2":(d) => f2(d)' in js
    assert "Plotly.toImage" in js and "window.Plotly" in js


def test_chart_opts_follow_r9():
    """Charts: laid out at their CSS size, rasterised at 220 dpi."""
    o = images.chart_opts("full", 0.56)
    assert o["width"] == 643 and o["scale"] == pytest.approx(220 / 96)
    assert round(o["width"] * o["scale"]) == pytest.approx(style.slot_px("full", 220), abs=2)


def test_figure_with_big_fixed_margins_keeps_its_plot():
    """Regression: Yvynation's deforestation timeline is designed 1183 px tall
    with 843 px of margins (context bands above, policy rows below). Forced to
    643×399 px it had no plot left — every series crushed onto one line."""
    fig = {"data": [{"type": "scatter", "y": [1, 2]}],
           "layout": {"height": 1183, "margin": {"t": 180, "b": 663, "l": 100, "r": 30}}}
    prepared = images.prepare_figure(fig, "full", 0.62)
    lay = prepared["layout"]
    plot_h = lay["height"] - 180 - 663
    assert plot_h >= 300                                   # the designed plot height survives
    assert lay["height"] / lay["width"] <= images.MAX_CHART_ASPECT + 1e-6
    o = images.figure_opts(prepared, "full")
    assert (o["width"], o["height"]) == (lay["width"], lay["height"])
    assert round(o["width"] * o["scale"]) == style.slot_px("full", style.CHART_DPI)


def test_ordinary_figure_keeps_the_slot_aspect():
    prepared = images.prepare_figure({"data": [], "layout": {"height": 800}}, "full", 0.56)
    assert (prepared["layout"]["width"], prepared["layout"]["height"]) == (643, 360)


def test_sankey_gets_compact_margins_unless_set():
    fig = {"data": [{"type": "sankey"}], "layout": {"title": {"text": "T"}}}
    m = images.prepare_figure(fig)["layout"]["margin"]
    assert m == {"l": 10, "r": 10, "b": 10, "t": 45}
    fig["layout"]["margin"] = {"l": 120}
    assert images.prepare_figure(fig)["layout"]["margin"]["l"] == 120


def test_prepare_figure_sets_page_ready_layout():
    fig = images.prepare_figure({"data": [{"name": str(i)} for i in range(8)],
                                 "layout": {"paper_bgcolor": "rgba(0,0,0,0)",
                                            "updatemenus": [{}]}})
    lay = fig["layout"]
    assert lay["paper_bgcolor"] == "#ffffff" and "updatemenus" not in lay
    assert lay["legend"]["orientation"] == "h"


# --- package rules ------------------------------------------------------------- #

def test_kit_is_python_311_syntax_and_self_contained():
    """Yvynation's image runs Python 3.11; the kit must never import its host."""
    for path in KIT.rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        ast.parse(src, filename=str(path), feature_version=(3, 11))
        assert not re.search(r"^\s*(from|import)\s+(naturametrics|camposcope|yvynation|reflex)\b",
                             src, re.M), path.name
        assert not re.search(r"^import ee\b|^from ee\b", src, re.M), \
            f"{path.name}: ee must be imported lazily"


def test_symbols_missing_from_noto_sans_still_reach_the_pdf():
    """The system Noto Sans has no − → ≥ ≤ ↳; reportlab dropped them silently
    ("−3,2" printed as "3,2"). The symbol subset now draws them."""
    import shutil
    import subprocess
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext not installed")
    meta = rk.ReportMeta(app="A", app_url="u", app_version="0", title="T",
                         subject="2008→2024", lang="pt")
    report = rk.Report(meta, [rk.Section("S", [
        rk.Paragraph("delta −3,2 p.p. · 2008→2024 · ≥ 10 · ↳ nota"),
        rk.ProvenanceTable([{"name": "n", "dataset_id": "d", "scale_m": 30,
                             "computed_at": "2026-09-25T05:46:00+00:00"}])])])
    text = subprocess.run(["pdftotext", "-", "-"], input=rk.render_pdf(report),
                          capture_output=True).stdout.decode()
    for piece in ("−3,2", "2008→2024", "≥ 10", "↳ nota"):
        assert piece in text, piece
    assert "2026-09-25 05:46" in text or "2026-09-25 05:46" in text   # one line
