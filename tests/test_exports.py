"""The export path, from the spreadsheet writer up.

The ODS writer exists because odfpy was too slow (see ``services/ods.py``), and a
hand-written format is exactly the kind of thing that works on the developer's
machine and produces a file LibreOffice refuses to open. So these tests read the
output back with an independent implementation — ``odfpy``, via pandas — rather
than trusting that what was written is what was meant.

The tests that need Earth Engine are marked ``ee`` and skipped without
credentials; everything else runs offline.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from naturametrics.services import ifn, ods  # noqa: E402


# --------------------------------------------------------------------------- #
# The writer
# --------------------------------------------------------------------------- #

def _read_back(data: bytes, tmp_path: Path):
    pd = pytest.importorskip("pandas")
    pytest.importorskip("odf", reason="odfpy is the independent reader")
    path = tmp_path / "out.ods"
    path.write_bytes(data)
    return pd.read_excel(path, sheet_name=None, engine="odf")


def test_ods_roundtrips_values_types_and_accents(tmp_path):
    sheets = [
        ods.Sheet("dados", ["texto", "inteiro", "decimal", "vazio"], [
            ["Formação Florestal & «quotes»", 42, 1.5, None],
            ["<script>", -7, -0.25, ""],
        ]),
        ods.Sheet("metadados", ["campo", "valor"], [["degradado", False]]),
    ]
    back = _read_back(ods.write(sheets), tmp_path)

    assert list(back) == ["dados", "metadados"]
    row = back["dados"].iloc[0]
    # Accents and XML-significant characters must survive unescaped in the cell.
    assert row["texto"] == "Formação Florestal & «quotes»"
    assert back["dados"].iloc[1]["texto"] == "<script>"
    # Numbers must arrive as numbers, not strings — a spreadsheet of text
    # right-aligned to look numeric is the classic silent export bug.
    assert row["inteiro"] == 42
    assert row["decimal"] == pytest.approx(1.5)
    assert back["metadados"].iloc[0]["valor"] == "não"


def test_ods_sheet_name_is_made_legal():
    sheet = ods.Sheet("uf/município[2024]*?:x" + "y" * 40, ["a"], [])
    assert not set(sheet.name) & set("[]*?:/\\")
    assert len(sheet.name) <= 31


def test_ods_refuses_a_sheet_no_spreadsheet_can_open():
    """Truncation would lose the tail silently, which is worse than failing."""
    too_many = ({"a": i} for i in range(ods.MAX_ROWS_PER_SHEET + 2))
    sheet = ods.Sheet("big", ["a"], ([r["a"]] for r in too_many))
    with pytest.raises(ods.SheetTooLarge):
        ods.write([sheet])


# --------------------------------------------------------------------------- #
# The selection the export covers
# --------------------------------------------------------------------------- #

def test_point_table_and_filter_index_agree():
    """Two files from one join. If they disagree, the count in the UI is a lie
    about the file the user is about to download."""
    if not ifn._load_points():
        pytest.skip("data/ifn_points_biome.csv not built")

    for filters in ({}, {"uf": "MT"}, {"biome": "Pantanal"},
                    {"uf": "MT", "biome": "Pantanal"},
                    {"uf": "MT", "municipality": "Cuiabá"}):
        assert len(ifn.selected_points(**filters)) == ifn.count(**filters), filters


def test_bbox_query_reports_truncation_rather_than_hiding_it():
    if not ifn._load_points():
        pytest.skip("data/ifn_points_biome.csv not built")

    whole_country = ifn.points_in_bbox(-74.0, -34.0, -33.0, 6.0, limit=10)
    assert whole_country["properties"]["returned"] == 10
    assert whole_country["properties"]["total"] > 10
    assert whole_country["properties"]["truncated"] is True


def test_bbox_query_excludes_points_outside_the_box():
    if not ifn._load_points():
        pytest.skip("data/ifn_points_biome.csv not built")

    box = ifn.points_in_bbox(-56.3, -15.9, -55.9, -15.4, uf="MT")
    for feature in box["features"]:
        lon, lat = feature["geometry"]["coordinates"]
        assert -56.3 <= lon <= -55.9 and -15.9 <= lat <= -15.4
        assert feature["properties"]["uf"] == "MT"


# --------------------------------------------------------------------------- #
# Whole workbooks
# --------------------------------------------------------------------------- #

@pytest.mark.ee
def test_study_point_workbook_has_a_tab_per_buffer_and_its_provenance(tmp_path):
    try:
        from naturametrics.services.ee_client import initialize_earth_engine
        initialize_earth_engine()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Earth Engine unavailable: {exc}")

    from naturametrics.config.settings import BUFFER_RADII_KM
    from naturametrics.services import exports
    from naturametrics.services.geo import point
    from naturametrics.services.mapbiomas_history import (
        land_cover_history, point_pixel_series,
    )

    p = point(lat=-15.48, lon=-56.16)
    history, history_prov = land_cover_history(p)
    pixel, pixel_prov = point_pixel_series(p)
    data, name = exports.study_point_workbook(
        p, history, history_prov, pixel, pixel_prov)

    assert name.endswith(".ods")
    back = _read_back(data, tmp_path)

    for radius in BUFFER_RADII_KM:
        assert f"buffer_{int(radius):02d}km" in back
    assert len(back["ponto_pixel"]) == 40

    # C6: the numbers never travel without the record of how they were made.
    # Empty spacer cells come back as NaN floats, so stringify per value rather
    # than relying on a frame-wide astype.
    joined = " ".join(str(v) for v in back["metadados"].to_numpy().ravel())
    assert "frequencyHistogram" in joined
    assert "mapbiomas" in joined.lower()


# --------------------------------------------------------------------------- #
# The state boundary
# --------------------------------------------------------------------------- #

def test_state_values_survive_the_trip_into_a_workbook():
    """Regression: Reflex hands mutables out of state wrapped in ``MutableProxy``.

    The wrapper is transparent to ``isinstance``, so a shallow ``dict(...)`` looks
    like it worked — and then ``dataclasses.asdict`` tries to *reconstruct* a
    nested list, calls ``MutableProxy(...)`` with no arguments, and the export
    dies deep inside provenance serialisation. Only a test that goes through a
    real state object catches it; every service-level test passes plain dicts and
    sees nothing.
    """
    import dataclasses

    from naturametrics.services.provenance import Provenance
    from naturametrics.state import AppState
    from naturametrics.state._proxy import plain

    prov = Provenance(
        name="landuse_history", dataset_id="asset", bands=["b1", "b2"],
        notes=["retried"], extra={"radii_km": [1, 2], "nested": {"k": [1]}},
    )
    state = AppState(_reflex_internal_init=True)
    state._provenance = prov.to_dict()
    state._history = [{"radius_km": 1.0, "year": 1985, "class_id": 3}]

    # The bug in miniature: proxied on the way out, and still proxied one level down.
    assert type(dict(state._provenance)["bands"]).__name__ == "MutableProxy"

    flat = plain(state._provenance)
    assert type(flat["bands"]) is list
    assert type(flat["extra"]["nested"]) is dict
    assert type(plain(state._history)[0]) is dict

    # The operation that actually failed.
    assert dataclasses.asdict(Provenance(**flat))["bands"] == ["b1", "b2"]


# --------------------------------------------------------------------------- #
# Multiple selection
# --------------------------------------------------------------------------- #

def _history_frame(radius, year, pairs):
    pd = pytest.importorskip("pandas")
    return pd.DataFrame([
        {"radius_km": radius, "year": year, "class_id": cid,
         "pixels": px, "area_ha": ha}
        for cid, px, ha in pairs
    ])


def test_aggregate_sums_per_radius_year_class():
    from naturametrics.services.mapbiomas_history import aggregate_histories

    a = _history_frame(10.0, 2024, [(3, 10.0, 1.0), (15, 5.0, 0.5)])
    b = _history_frame(10.0, 2024, [(3, 20.0, 2.0)])
    agg = aggregate_histories([a, b]).set_index("class_id")

    assert agg.loc[3, "area_ha"] == pytest.approx(3.0)
    assert agg.loc[3, "pixels"] == pytest.approx(30.0)
    # A class present in only one member still appears, at its own value.
    assert agg.loc[15, "area_ha"] == pytest.approx(0.5)
    # Labels are re-derived, so the aggregate is readable without a join.
    assert agg.loc[3, "class_pt"] and agg.loc[3, "color"].startswith("#")


def test_aggregate_keeps_radii_and_years_separate():
    """The sum is per buffer and per year — never pooled across either."""
    from naturametrics.services.mapbiomas_history import aggregate_histories

    frames = [_history_frame(1.0, 2024, [(3, 1.0, 1.0)]),
              _history_frame(10.0, 2024, [(3, 1.0, 1.0)]),
              _history_frame(10.0, 1985, [(3, 1.0, 1.0)])]
    agg = aggregate_histories(frames)

    assert len(agg) == 3
    assert set(agg["radius_km"]) == {1.0, 10.0}
    assert set(agg["year"]) == {1985, 2024}


def test_aggregate_of_nothing_is_an_empty_frame_not_a_crash():
    from naturametrics.services.mapbiomas_history import aggregate_histories

    empty = aggregate_histories([])
    assert empty.empty
    # Columns still present, so callers can index it without special-casing.
    for column in ("radius_km", "year", "class_id", "area_ha"):
        assert column in empty.columns


def test_manual_selection_names_the_same_points_the_filters_would():
    """A manual spec and a filter spec must resolve to one definition of
    "the selection" — the export's tabs are built from `points()` while the
    Earth Engine query is built from `collection()`, and they cannot disagree."""
    from naturametrics.services import exports

    if not ifn._load_points():
        pytest.skip("data/ifn_points_biome.csv not built")

    by_filter = exports.SelectionSpec(uf="MT", municipality="Cuiabá")
    names = [r["conglomerado"] for r in by_filter.points()]
    manual = exports.SelectionSpec(conglomerados=names)

    assert not by_filter.is_manual and manual.is_manual
    assert [r["conglomerado"] for r in manual.points()] == names
    # The manual label still records what the map filters were showing.
    assert "seleção manual" in manual.filter_label()


# --------------------------------------------------------------------------- #
# Earth Engine initialisation
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("entry", ["land_cover_history", "point_pixel_series",
                                   "preview_land_cover"])
def test_analysis_entry_points_initialise_earth_engine(monkeypatch, entry):
    """Regression: an analysis must not assume someone else initialised EE.

    A browser tab left open across a backend restart never re-runs the app's
    ``on_mount`` initialiser, so in the new process Earth Engine is
    uninitialised. Tile layers self-heal because ``tiles.get_tile_url`` calls
    ``get_ee()``; the analyses did not, so every call raised
    "Earth Engine client library not initialized" and a selection of two dozen
    conglomerados failed in full — looking like broken data rather than a stale
    session.

    Uses an out-of-Brazil coordinate so validation rejects it immediately: the
    check is that initialisation was ensured *before* anything else, and no
    network call is made either way.
    """
    from naturametrics.services import ee_client, mapbiomas_history
    from naturametrics.services.geo import CoordinateError, point

    calls = []
    monkeypatch.setattr(ee_client, "_initialized", False)
    monkeypatch.setattr(ee_client, "initialize_earth_engine",
                        lambda: calls.append(entry))

    fn = getattr(mapbiomas_history, entry)
    with pytest.raises(CoordinateError):
        fn(point(lat=48.85, lon=2.35))  # Paris

    assert calls == [entry], f"{entry} must call get_ee() before doing anything"


# --------------------------------------------------------------------------- #
# Buffer capacity and the per-radius tabs
# --------------------------------------------------------------------------- #

def test_estimate_scales_with_radii_and_points():
    """The panel reports cost; it does not refuse. Fewer radii must mean fewer
    rows, a smaller file and less time — that is the whole reason the radius
    selector exists."""
    from naturametrics.services import exports

    one = exports.buffer_estimate(1000, [1.0])
    four = exports.buffer_estimate(1000, [1.0, 2.0, 5.0, 10.0])

    assert one["rows"] < four["rows"]
    assert one["megabytes"] < four["megabytes"]
    assert one["tabs"] == 1 and four["tabs"] == 4
    # Time is per conglomerado, so it does not change with the radius count.
    assert one["seconds"] == four["seconds"]


def test_size_alone_never_refuses_below_the_point_limit():
    """No size ceiling exists in the ODS format, so none is invented. A big but
    permitted selection is split into more tabs and warned about, not blocked."""
    from naturametrics.services import exports
    from naturametrics.config import settings as st

    n = st.EXPORT_MAX_BUFFER_POINTS
    est = exports.buffer_estimate(n, [1.0, 2.0, 5.0, 10.0])
    assert est["heavy"] and est["split"] and not est["over_limit"]
    assert est["tabs"] > 4          # split into extra parts rather than refused

    message = exports.buffer_estimate_message(n, [1.0, 2.0, 5.0, 10.0])
    assert "dividido" in message    # says the tabs will be split
    assert "pode ficar" in message  # warns, in the conditional


def test_the_point_limit_clears_the_largest_biome():
    """The ceiling has a reason from the data: it must fit any whole biome.

    Amazônia is the largest at 5 801 conglomerados. If the point table or the
    limit ever moves such that a biome no longer fits, that is a decision to
    make deliberately, not to discover in the field.
    """
    from naturametrics.config import settings as st

    if not ifn._load_points():
        pytest.skip("data/ifn_points_biome.csv not built")

    from collections import Counter
    per_biome = Counter(r["bioma"] for r in ifn._load_points() if r["bioma"])
    assert max(per_biome.values()) <= st.EXPORT_MAX_BUFFER_POINTS

    # And every single state, which is the other common whole-unit selection.
    per_uf = Counter(r["uf"] for r in ifn._load_points() if r["uf"])
    assert max(per_uf.values()) <= st.EXPORT_MAX_BUFFER_POINTS


def test_over_the_limit_refuses_and_points_at_the_remedy():
    from naturametrics.services import exports
    from naturametrics.config import settings as st

    over = st.EXPORT_MAX_BUFFER_POINTS + 1
    assert exports.buffer_estimate(over, [1.0])["over_limit"]

    message = exports.buffer_estimate_message(over, [1.0])
    assert "limite" in message
    assert "filtros" in message              # what to do about it
    assert "não têm limite" in message       # what still works unrestricted


def test_heavy_flag_tracks_the_configured_warning_size(monkeypatch):
    from naturametrics.services import exports

    small = exports.buffer_estimate(10, [1.0])
    assert not small["heavy"]

    monkeypatch.setattr(exports, "EXPORT_WARN_FILE_MB", 0)
    assert exports.buffer_estimate(10, [1.0])["heavy"]


def test_buffer_tabs_are_split_per_radius_and_drop_the_radius_column():
    from naturametrics.services import exports

    pd = pytest.importorskip("pandas")
    rows = []
    for radius in (1.0, 10.0):
        for year in (1985, 2024):
            rows.append({"conglomerado": "X_1", "uf": "MT", "municipio": "M",
                         "bioma": "Cerrado", "radius_km": radius, "year": year,
                         "class_id": 3, "class_pt": "a", "class_en": "b",
                         "pixels": 1.0, "area_ha": 1.0, "area_pct": 100.0})
    sheets = exports._buffer_sheets(pd.DataFrame(rows), [1.0, 10.0])

    assert [s.name for s in sheets] == ["buffer_01km", "buffer_10km"]
    # The tab name carries the radius, so the column would be dead weight across
    # a million rows.
    assert "radius_km" not in sheets[0].header


def test_an_oversized_radius_is_split_rather_than_refused(monkeypatch):
    """The row budgets are estimates. An estimate that comes in low must not
    destroy an export that has already cost minutes of Earth Engine time."""
    from naturametrics.services import exports

    pd = pytest.importorskip("pandas")
    monkeypatch.setattr(exports, "EXPORT_ODS_ROWS_PER_SHEET", 10)

    frame = pd.DataFrame([
        {"conglomerado": f"X_{i}", "uf": "MT", "municipio": "M",
         "bioma": "Cerrado", "radius_km": 10.0, "year": 1985 + i,
         "class_id": 3, "class_pt": "a", "class_en": "b",
         "pixels": 1.0, "area_ha": 1.0, "area_pct": 100.0}
        for i in range(25)
    ])
    sheets = exports._buffer_sheets(frame, [10.0])

    assert [s.name for s in sheets] == ["buffer_10km", "buffer_10km_2",
                                        "buffer_10km_3"]
    # Continuous, not overlapping: stacking the parts rebuilds the original.
    total = sum(len(list(s.rows)) for s in sheets)
    assert total == 25
