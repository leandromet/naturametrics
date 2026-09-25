"""The report must describe what the charts show (doc/14 §1, bug 1).

Regression: with a multi-selection on screen the HTML report read the stale
single-point frames (``self._history`` & co.) and described the *previous
point*. The state now picks rows with the same three-way switch as
``_chart_records``; this pins that switch without spinning up Reflex, by
calling the plain methods on a stand-in object.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from naturametrics.state._export import ExportMixin  # noqa: E402

_pick = ExportMixin._mode_pick
_is_selection = ExportMixin._report_is_selection


def _s(**kw):
    base = dict(multi_mode=False, multi_view_mode="sum", _multi_history=[])
    base.update(kw)
    return SimpleNamespace(**base)


ROWS = (["bbox"], {"p": "bbox"}, ["multi"], {"p": "multi"}, ["single"], {"p": "single"})


def test_single_point_reads_single_frames():
    assert _pick(_s(), *ROWS) == (["single"], {"p": "single"})


def test_multi_sum_reads_the_selection_not_the_stale_point():
    s = _s(multi_mode=True, _multi_history=[{"x": 1}])
    assert _pick(s, *ROWS) == (["multi"], {"p": "multi"})
    assert _is_selection(s) is True


def test_multi_full_area_reads_the_bbox():
    s = _s(multi_mode=True, multi_view_mode="full_area", _multi_history=[{"x": 1}])
    assert _pick(s, *ROWS) == (["bbox"], {"p": "bbox"})


def test_multi_mode_without_a_measured_selection_falls_back_like_the_chart():
    """Multi mode on but nothing measured yet: the chart still shows the
    point (_chart_records falls through), so the report does too."""
    s = _s(multi_mode=True)
    assert _pick(s, [], {}, [], {}, ["single"], {"p": "single"}) == (
        ["single"], {"p": "single"})
    assert _is_selection(s) is False


# --- the report snapshot (doc/14 §11: "with multi mode on and a stale
# single-point result, the report is the selection's, never the point's") --- #

def _snapshot_state(**kw):
    import types
    hist = [{"radius_km": 5.0, "year": y, "class_id": 3, "area_ha": 10.0}
            for y in (1985, 2024)]
    stale = [{"radius_km": 5.0, "year": y, "class_id": 15, "area_ha": 99.0}
             for y in (1985, 2024)]
    base = dict(
        multi_mode=True, multi_view_mode="sum", _multi_history=hist,
        _multi_provenance={"name": "multi"}, _multi_bbox_history=[],
        _multi_bbox_provenance={}, _history=stale, _provenance={"name": "stale"},
        study_lat=-12.0, study_lon=-55.0, point_source="clique no mapa",
        point_conglomerado="999", point_uf="MT", point_municipio="X", point_bioma="Y",
        buffer_shape="circle", _chart_radius=5.0, age_effective_radius=5.0,
        buffer_overlays={}, multi_error="", analysis_error="", age_error="",
        landscape_metrics_error="", biomass_error="", veg_compare_error="",
        connectivity_error="", gbif_buffer_error="",
        _multi_coords={"101": [-12.1, -55.1], "102": [-12.2, -55.2]},
        _multi_meta={"101": {"key": "101", "conglomerado": "101", "place": "A · MT", "bioma": "B"},
                     "102": {"key": "102", "conglomerado": "102", "place": "C · MT", "bioma": "B"}},
        _multi_frames={"101": hist, "102": hist},
        _pixel=[{"year": 1985}], _pixel_provenance={}, _age_point=[], _age_point_provenance={},
        _change_stats={"5": {"loss_ha": 1.0}}, _change_provenance={},
        _connectivity=[], _connectivity_provenance={}, _gbif_buffer_point=[],
        gbif_buffer_rows=[],
    )
    for name in ("age_history", "landscape_metrics", "biomass", "veg_compare"):
        base[f"_multi_bbox_{name}"] = []
        base[f"_multi_{name}"] = []
    for name in ("age", "landscape", "biomass", "veg_compare"):
        base[f"_multi_bbox_{name}_provenance"] = {}
        base[f"_multi_{name}_provenance"] = {}
    base.update(_age_buffers=[], _age_buffers_provenance={}, _landscape_metrics=[],
                _landscape_metrics_provenance={}, _biomass=[], _biomass_provenance={},
                _veg_compare=[], _veg_compare_provenance={})
    base.update(kw)
    s = SimpleNamespace(**base)
    s._mode_pick = types.MethodType(ExportMixin._mode_pick, s)
    s._report_is_selection = types.MethodType(ExportMixin._report_is_selection, s)
    return s


def test_snapshot_in_multi_mode_is_the_selection_not_the_stale_point():
    from naturametrics.services.report import ReportData, build_report, report_filename

    snap = ExportMixin._report_snapshot(_snapshot_state())
    assert snap["kind"] == "selection"
    assert snap["history_prov"] == {"name": "multi"}
    assert [p["conglomerado"] for p in snap["points"]] == ["101", "102"]
    assert snap["points"][0]["lat"] == -12.1
    # Point-only products are not carried into a selection's snapshot.
    assert "pixel" not in snap and "change" not in snap
    d = ReportData.from_snapshot(snap)
    report = build_report(d)
    assert "2 conglomerado" in report.meta.subject
    assert "999" not in report_filename(d, "pdf")


def test_snapshot_single_point_carries_point_products():
    snap = ExportMixin._report_snapshot(_snapshot_state(multi_mode=False))
    assert snap["kind"] == "point"
    assert snap["history_prov"] == {"name": "stale"}
    assert snap["pixel"] == [{"year": 1985}] and snap["change"]
    assert "gbif_rows" not in snap      # surveyed elsewhere (or never)


def test_pending_report_is_bound_to_its_client_token():
    from naturametrics.state._export import _PendingReport, _PendingStore
    store = _PendingStore()
    store.put("job", "tok-a", _PendingReport(data=None, opts=None, lang="pt", specs=[], fmt="pdf"))
    assert store.take("job", "tok-b") is None        # a foreign client cannot claim it
    assert store.take("job", "tok-a") is not None
    assert store.take("job", "tok-a") is None        # taken once
