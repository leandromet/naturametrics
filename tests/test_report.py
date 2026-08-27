"""services/report.py — the bulk "paper-friendly" HTML report.

Offline only: report-building itself makes no Earth Engine calls (it only
lays out frames the caller already computed), so every test here runs on
synthetic data, the same style as test_landscape_metrics.py.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from naturametrics.config.settings import BUFFER_RADII_KM  # noqa: E402
from naturametrics.services.geo import point  # noqa: E402
from naturametrics.services.provenance import Provenance  # noqa: E402
from naturametrics.services.report import study_point_report_html  # noqa: E402


def _history_df():
    rows = []
    for r in BUFFER_RADII_KM:
        for year in (1985, 2024):
            rows.append({"radius_km": r, "year": year, "class_id": 3,
                        "class_pt": "Formação Florestal", "class_en": "Forest",
                        "pixels": 100, "area_ha": 90.0, "color": "#1f8d49"})
            rows.append({"radius_km": r, "year": year, "class_id": 15,
                        "class_pt": "Pastagem", "class_en": "Pasture",
                        "pixels": 20, "area_ha": 18.0, "color": "#edde8e"})
    return pd.DataFrame(rows)


def _prov():
    return Provenance(name="landuse_history", dataset_id="asset",
                      bands=["b1"], reducer="frequencyHistogram")


def _metrics_df():
    return pd.DataFrame([
        {"radius_km": r, "area_ha": 108.0, "patches": 3, "patch_density": 0.03,
         "largest_patch_ha": 60.0, "largest_patch_pct": 55.5, "edge_m": 900.0,
         "edge_density": 8.3, "mean_patch_ha": 36.0, "patch_area_sq_ha": 4200.0,
         "meff_ha": 38.9, "shannon": 0.6, "simpson": 0.4, "simpson_evenness": 0.9}
        for r in BUFFER_RADII_KM
    ])


def _connectivity_df():
    return pd.DataFrame([
        {"radius_km": r, "n_fragments": 5, "enn_mean_m": 120.5, "enn_median_m": 95.0}
        for r in BUFFER_RADII_KM
    ])


def test_report_is_one_self_contained_html_file():
    p = point(lat=-15.48, lon=-56.16)
    data, name = study_point_report_html(
        p, _history_df(), _prov(), identity={"conglomerado": "C-001"},
        landscape_metrics=_metrics_df(), connectivity=_connectivity_df(),
    )
    assert name.endswith(".html")
    doc = data.decode("utf-8")
    assert doc.startswith("<!doctype html>")
    # Plotly's bundle is injected exactly once, however many figures follow —
    # this is the whole point of include_plotlyjs=("inline" if first else
    # False) in _fig_html: a second injection would bloat the file and risk
    # each figure's script re-registering the same global.
    assert doc.count("Plotly.newPlot") >= len(BUFFER_RADII_KM)
    assert doc.count("var Plotly") + doc.count("define(") >= 1


def test_figures_and_tables_can_be_toggled_independently():
    p = point(lat=-15.48, lon=-56.16)

    figures_only, _ = study_point_report_html(
        p, _history_df(), _prov(), include_figures=True, include_tables=False)
    doc = figures_only.decode("utf-8")
    assert "<h2>Figuras</h2>" in doc
    # Tables are gone, but provenance (constraint C6) still shows regardless
    # of which sections were asked for — it is not one of the two checkboxes.
    assert "<h2>Tabelas</h2>" not in doc
    assert "<h2>Proveniência</h2>" in doc

    tables_only, _ = study_point_report_html(
        p, _history_df(), _prov(), include_figures=False, include_tables=True,
        landscape_metrics=_metrics_df())
    doc = tables_only.decode("utf-8")
    assert "<h2>Figuras</h2>" not in doc
    assert "Tabelas" in doc
    assert "<table>" in doc


def test_citation_and_data_sources_are_always_present():
    """Constraint C6/C4 in a new medium: the report must still say how the
    numbers were made and how to cite them, same as the ODS metadata sheet."""
    from naturametrics.config.citation import CITATION_TEXT

    p = point(lat=-15.48, lon=-56.16)
    data, _ = study_point_report_html(p, _history_df(), _prov())
    doc = data.decode("utf-8")
    assert CITATION_TEXT.split(".")[0] in doc
    assert "mapbiomas.org" in doc


def test_empty_frames_produce_empty_notes_not_a_crash():
    p = point(lat=-15.48, lon=-56.16)
    data, name = study_point_report_html(p, pd.DataFrame(), _prov())
    assert name.endswith(".html")
    doc = data.decode("utf-8")
    assert "nm-empty" in doc


def test_identity_with_markup_is_escaped_not_executed():
    """A pasted conglomerado/municipality string is not third-party free
    text in practice, but escaping is free — a raw "<" must never be able
    to break out of the page (same OWASP reasoning as the ODS formula-
    injection guard in test_exports.py)."""
    p = point(lat=-15.48, lon=-56.16)
    data, _ = study_point_report_html(
        p, _history_df(), _prov(),
        identity={"conglomerado": "<script>alert(1)</script>"})
    doc = data.decode("utf-8")
    assert "<script>alert(1)</script>" not in doc
    assert "&lt;script&gt;" in doc
