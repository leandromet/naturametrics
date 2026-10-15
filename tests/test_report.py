"""services/report.py — the laid-out report model (doc/14 §3, §11).

Offline only: the model builders make no Earth Engine calls (maps are passed
in, and absent here), so every test runs on synthetic frames. Both renderers
are exercised end to end — the PDF with placeholder figures (no browser in a
test), the HTML with interactive ones.
"""

import re
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("reportlab")

from naturametrics import report_kit as rk  # noqa: E402
from naturametrics.config.settings import BUFFER_RADII_KM  # noqa: E402
from naturametrics.services import report_text as rt  # noqa: E402
from naturametrics.services.report import (  # noqa: E402
    ReportData, ReportOptions, _radii_in, build_report, build_selection_report,
    build_study_point_report, figure_specs, map_frame, render_report,
    report_filename, resolve_figures,
)

RADII = sorted(BUFFER_RADII_KM)


def _history(radii=RADII):
    rows = []
    for r in radii:
        for year in (1985, 2000, 2024):
            forest = 90.0 * r if year == 1985 else 60.0 * r
            rows.append({"radius_km": r, "year": year, "class_id": 3,
                         "class_pt": "Formação Florestal", "class_en": "Forest Formation",
                         "pixels": 100, "area_ha": forest, "color": "#1f8d49"})
            rows.append({"radius_km": r, "year": year, "class_id": 15,
                         "class_pt": "Pastagem", "class_en": "Pasture",
                         "pixels": 20, "area_ha": 120.0 * r - forest, "color": "#edde8e"})
    return pd.DataFrame(rows)


def _age(radii=RADII):
    rows = []
    for r in radii:
        rows += [
            {"radius_km": r, "age": 3, "bin": "0–5 anos", "censored": False,
             "pixels": 10, "area_ha": 10.0 * r, "color": "#aaa"},
            {"radius_km": r, "age": 18, "bin": "11–20 anos", "censored": False,
             "pixels": 10, "area_ha": 20.0 * r, "color": "#bbb"},
            {"radius_km": r, "age": 39, "bin": "≥ 39 (natural desde 1986)", "censored": True,
             "pixels": 10, "area_ha": 30.0 * r, "color": "#ccc"},
        ]
    return pd.DataFrame(rows)


def _biomass(radii=RADII):
    return pd.DataFrame([{"radius_km": r, "year": y, "agb_mean_mgha": 100.0 - (y - 2007),
                          "agb_sd_mgha": 5.0, "area_ha": 100.0 * r,
                          "total_biomass_mg": 1e4 * r}
                         for r in radii for y in (2007, 2010, 2022)])


def _metrics(radii=RADII):
    return pd.DataFrame([
        {"radius_km": r, "area_ha": 108.0, "patches": 3, "patch_density": 0.03,
         "largest_patch_ha": 60.0, "largest_patch_pct": 55.5, "edge_m": 900.0,
         "edge_density": 8.3, "mean_patch_ha": 36.0, "patch_area_sq_ha": 4200.0,
         "meff_ha": 38.9, "shannon": 0.6, "simpson": 0.4, "simpson_evenness": 0.9}
        for r in radii])


def _prov(name="landuse_history"):
    return {"name": name, "dataset_id": "projects/mapbiomas/asset", "bands": ["b1985"],
            "scale_m": 30, "reducer": "frequencyHistogram", "degraded": False,
            "computed_at": "2026-09-24T12:00:00+00:00", "notes": []}


def _point(**kw):
    base = dict(
        kind="point", lat=-12.55, lon=-55.72,
        identity={"conglomerado": "C-001", "uf": "MT", "municipio": "Sorriso",
                  "bioma": "Amazônia"},
        active_radius=5.0, age_radius=1.0,
        history=_history(), history_prov=_prov(),
        pixel=pd.DataFrame([{"year": y, "class_id": 3 if y < 2005 else 15,
                             "class_pt": "Formação Florestal" if y < 2005 else "Pastagem",
                             "class_en": "Forest Formation" if y < 2005 else "Pasture"}
                            for y in range(1985, 2025)]),
        pixel_prov=_prov("pixel"),
        age_point=pd.DataFrame([{"year": y, "age": y - 1985, "color": "#1f8d49",
                                 "class_pt": "F", "class_en": "F"} for y in range(1986, 2025)]),
        age_buffers=_age(), age_buffers_prov=_prov("vegetation_age"),
        change={r: {"loss_ha": 84.0, "gain_ha": 31.0, "stable_ha": 500.0} for r in RADII},
        change_prov=_prov("change_stats"),
        landscape_metrics=_metrics(), landscape_metrics_prov=_prov("landscape"),
        biomass=_biomass(), biomass_prov=_prov("biomass"),
    )
    base.update(kw)
    return ReportData(**base)


def _selection(mode="sum", n=3):
    radii = [max(RADII)] if mode == "full_area" else RADII
    pts = [{"key": str(100 + i), "conglomerado": str(100 + i), "place": "Sorriso · MT",
            "bioma": "Amazônia", "lat": -12.5 - i * 0.1, "lon": -55.7}
           for i in range(n)]
    return ReportData(
        kind="selection", selection_mode=mode, points=pts,
        point_frames={p["key"]: _history().to_dict("records") for p in pts},
        lat=-99.0, lon=-99.0, identity={"conglomerado": "999"},   # a stale point
        active_radius=5.0, age_radius=5.0,
        history=_history(radii), history_prov=_prov(),
        age_buffers=_age(radii), biomass=_biomass(radii),
        landscape_metrics=_metrics(radii))


def _titles(report):
    return [s.title for s in report.sections]


def _status(report, title_key, lang="pt"):
    title = rt.tx(title_key, lang)
    items = next(b for s in report.sections for b in s.blocks
                 if isinstance(b, rk.ContentsList)).items
    return next(i for i in items if i.title == title).status


def _all_text(report) -> str:
    out = [report.meta.title, report.meta.subject]
    for s in report.sections:
        out.append(s.title)
        for b in s.blocks:
            for x in ([b.left, b.right] if isinstance(b, rk.SideBySide) else [b]):
                if isinstance(x, (rk.Paragraph, rk.Callout)):
                    out.append(x.text)
                elif isinstance(x, rk.Table):
                    out += [x.caption, x.note] + [str(c) for c in x.columns]
                    out += [str(v) for row in x.rows for v in row]
                elif isinstance(x, rk.KeyValues):
                    out += [f"{k} {v}" for k, v in x.rows]
                elif isinstance(x, (rk.Figure, rk.MapFigure)):
                    out.append(x.caption)
                elif isinstance(x, rk.ContentsList):
                    out += [f"{i.title} {i.reason}" for i in x.items]
                elif isinstance(x, rk.LocatorMap):
                    out.append(x.label)
    return "\n".join(out)


# --- study point ------------------------------------------------------------ #

def test_study_point_section_order_follows_doc_3a():
    report = build_study_point_report(_point(), ReportOptions(appendix=True))
    t = lambda k: rt.tx(k, "pt")  # noqa: E731
    assert _titles(report) == [
        t("sec_identification"), t("sec_about"), t("sec_land_cover"), t("sec_pixel"),
        t("sec_age"), t("sec_change"), t("sec_biomass"), t("sec_landscape"),
        t("sec_provenance"), t("sec_sources"), t("sec_appendix")]


def test_statuses_excluded_not_run_and_unavailable():
    d = _point(errors={"veg_compare": "timeout"})
    report = build_study_point_report(d, ReportOptions(maps=False, gbif=False))
    assert _status(report, "sec_maps") == "excluded"          # unticked
    assert _status(report, "sec_gbif") == "excluded"          # unticked
    assert _status(report, "sec_connectivity") == "not_run"   # its own button
    assert _status(report, "sec_ibge") == "unavailable"       # failed on screen
    assert _status(report, "sec_appendix") == "excluded"
    assert _status(report, "sec_land_cover") == "included"
    # Maps ticked but never fetched (no Earth Engine here) is stated, not hidden.
    report = build_study_point_report(_point(), ReportOptions(maps=True))
    assert _status(report, "sec_maps") == "unavailable"
    # GBIF ticked but never surveyed.
    report = build_study_point_report(_point(), ReportOptions(gbif=True))
    assert _status(report, "sec_gbif") == "not_run"


def test_gbif_section_when_ticked_and_surveyed():
    rows = [{"radius_km": r, "total": 10 * i, "richness": 3 * i,
             "species": [{"name": "Tapirus terrestris", "count": 4}]}
            for i, r in enumerate(RADII, 1)]
    report = build_study_point_report(_point(gbif_rows=rows), ReportOptions(gbif=True))
    assert _status(report, "sec_gbif") == "included"
    assert "Tapirus terrestris" in _all_text(report)


def test_age_sentence_states_the_censored_share():
    """Constraint C5: an age figure without its censored share does not ship."""
    report = build_study_point_report(_point())
    text = _all_text(report)
    assert "censurada: pelo menos" in text
    assert "50,0 %" in text          # 30 of 60 ha censored at every radius


def test_radii_come_from_the_data_not_the_config():
    """Full-area mode carries only the outer radius; looping BUFFER_RADII_KM
    drew one empty figure per missing radius."""
    outer = max(RADII)
    d = _point(history=_history([outer]), age_buffers=_age([outer]),
               biomass=_biomass([outer]), landscape_metrics=_metrics([outer]),
               change={}, active_radius=1.0, age_radius=1.0)
    assert _radii_in(d.history) == [outer]
    report = build_study_point_report(d)
    caps = [b.caption for b in report.blocks() if isinstance(b, rk.Figure)]
    assert caps and all(f"{outer:g} km" in c for c in caps if "buffer" in c)
    tables = [b for b in report.blocks() if isinstance(b, rk.Table)]
    first_cols = {str(row[0]) for tb in tables for row in tb.rows}
    assert "1 km" not in first_cols and "0,5 km" not in first_cols


def test_identity_with_markup_is_escaped_not_executed():
    d = _point(identity={"conglomerado": "<script>alert(1)</script>"})
    html = render_report(build_study_point_report(d), "html").decode("utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_citation_and_sources_by_language():
    from naturametrics.config.citation import CITATION_TEXT
    pt = _all_text(build_study_point_report(_point(), lang="pt"))
    en_report = build_study_point_report(_point(), lang="en")
    citation = next(b for b in en_report.blocks() if isinstance(b, rk.Citation))
    assert CITATION_TEXT.split(".")[0] in citation.text
    assert "Disponível" not in citation.text and "Available at" in citation.text
    assert any("Collection 11" in s for s in citation.sources)
    assert not any("Coleção" in s for s in citation.sources)
    assert any("mapbiomas.org" in s for s in citation.sources)
    assert "Como citar" not in pt   # the kit prints that heading, not the model


def test_english_report_has_no_portuguese_template_text():
    """Every pt template that has an en version must not leak into an en
    report. Verbatim identifiers (class labels from data, dataset ids,
    provenance names) are exempt — they are not template text."""
    for d, build in ((_point(), build_study_point_report),
                     (_selection("sum"), build_selection_report),
                     (_selection("full_area"), build_selection_report)):
        text = _all_text(build(d, ReportOptions(appendix=True), lang="en"))
        for key, pt in rt._PT.items():
            if rt._EN.get(key) == pt or len(pt) < 12:
                continue
            probe = re.split(r"\{[^}]*\}", pt)
            probe = max(probe, key=len).strip()
            if len(probe) >= 15 and " " in probe:
                assert probe not in text, (key, probe)


def test_every_pt_template_has_an_english_version():
    assert set(rt._PT) == set(rt._EN)


# --- selection ----------------------------------------------------------------- #

def test_selection_report_describes_the_selection_not_the_stale_point():
    """Regression (doc/14 §1): with a multi-selection on screen the report once
    described the *previous single point*."""
    d = _selection("sum")
    report = build_selection_report(d)
    text = _all_text(report)
    assert "Seleção de 3 conglomerado(s)" in report.meta.subject
    assert "-99.00000" not in text and "999" not in report_filename(d, "pdf")
    assert report_filename(d, "pdf").startswith("naturametrics_selecao_3_")
    assert "contada uma vez por conglomerado" in text      # overlap caveat, sum mode
    for c in ("100", "101", "102"):
        assert c in text
    assert _status(report, "sec_change") == "unavailable"
    assert _status(report, "sec_pixel") == "unavailable"
    assert _status(report, "sec_connectivity") == "unavailable"
    assert rt.tx("sec_per_point") in _titles(report)


def test_full_area_selection_has_one_radius_and_no_overlap_caveat():
    d = _selection("full_area")
    report = build_selection_report(d, lang="en")
    text = _all_text(report)
    assert "full area" in report.meta.subject
    assert "counted once per conglomerado" not in text
    assert _radii_in(d.history) == [max(RADII)]
    specs = figure_specs(d, "en")
    assert specs and all(f"{max(RADII):g} km" in s.caption for s in specs)


def test_build_report_dispatches_on_kind():
    assert build_report(_selection()).meta.title == rt.tx("title_selection")
    assert build_report(_point()).meta.title == rt.tx("title")


# --- maps, figures, rendering ---------------------------------------------- #

def test_map_frame_uses_buffer_overlays_and_multi_circles():
    from naturametrics.services.buffers import buffer_circles_geojson, buffer_geojson
    from naturametrics.services.geo import point
    d = _point(overlays=buffer_geojson(point(lat=-12.55, lon=-55.72), tuple(RADII)))
    frame = map_frame(d)
    assert len(frame.rings["features"]) == len(RADII) and frame.clip is not None
    assert frame.view.longest_side_km < 50        # Sentinel-2 backdrop range
    sel = _selection("sum")
    sel.overlays = buffer_circles_geojson([(p["lat"], p["lon"]) for p in sel.points],
                                          tuple(RADII))
    frame = map_frame(sel)
    assert len(frame.rings["features"]) == 3      # the outer ring per point
    assert len(frame.points["features"]) == 3
    assert frame.clip is None and not frame.backdrop


@pytest.mark.parametrize("fmt", ["pdf", "html"])
@pytest.mark.parametrize("make", [_point, lambda: _selection("sum"),
                                  lambda: _selection("full_area")])
def test_renders_to_bytes_within_budget(fmt, make):
    d = make()
    specs = figure_specs(d, "pt")
    assert specs
    figures = resolve_figures(specs, fmt, pngs={}, errors={s.key: "timeout" for s in specs})
    report = build_report(d, ReportOptions(appendix=True), "pt", figures=figures)
    data = render_report(report, fmt)
    if fmt == "pdf":
        assert len(data) <= 3_000_000      # R9; the HTML inlines Plotly (≈4.5 MB, §8)
        assert data[:5] == b"%PDF-"
        # A chart the browser never returned is a stated placeholder.
        assert all(f.png is None and f.unavailable_reason for f in figures.values())
    else:
        assert data.decode("utf-8").startswith("<!doctype html>")


def test_filename_follows_the_common_pattern():
    from datetime import datetime, timezone
    when = datetime(2026, 9, 24, 15, 30, tzinfo=timezone.utc)
    assert report_filename(_point(), "pdf", when) == "naturametrics_C-001_20260924-1530.pdf"
    d = _point(identity={})
    assert report_filename(d, "html", when) == "naturametrics_s12.5500_s55.7200_20260924-1530.html"
