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
    from naturametrics.state._export import _plain

    prov = Provenance(
        name="landuse_history", dataset_id="asset", bands=["b1", "b2"],
        notes=["retried"], extra={"radii_km": [1, 2], "nested": {"k": [1]}},
    )
    state = AppState(_reflex_internal_init=True)
    state._provenance = prov.to_dict()
    state._history = [{"radius_km": 1.0, "year": 1985, "class_id": 3}]

    # The bug in miniature: proxied on the way out, and still proxied one level down.
    assert type(dict(state._provenance)["bands"]).__name__ == "MutableProxy"

    plain = _plain(state._provenance)
    assert type(plain["bands"]) is list
    assert type(plain["extra"]["nested"]) is dict
    assert type(_plain(state._history)[0]) is dict

    # The operation that actually failed.
    assert dataclasses.asdict(Provenance(**plain))["bands"] == ["b1", "b2"]
