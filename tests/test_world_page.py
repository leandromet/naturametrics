"""The world page's logic, without Earth Engine or the bucket: GLC tile names and legend, the block
lookup, the Climate tab's rows (stubbed readers), the coordinate check and the geocoder."""

import pytest

from naturametrics.world.config import disturbance as dcfg
from naturametrics.world.config import glc
from naturametrics.world.services import climate_blocks as cb
from naturametrics.world.services import climate_rows, geo, geocode, glc_earth, glc_history
from naturametrics.world.services.koppen_labels import KOPPEN


def test_tile_names_use_the_north_edge():
    assert glc_earth.tile_bounds("GLC_FCS30D_20002022_E5N5_Annual") == (5, 0, 10, 5)
    assert glc_earth.tile_bounds("GLC_FCS30D_20002022_W60S10_Annual") == (-60, -15, -55, -10)
    assert glc_earth.tile_covering(9.189, 8.668) == "GLC_FCS30D_20002022_E5N10_Annual"
    assert glc_earth.tile_covering(-40.0, -30.0) is None          # open ocean: no tile


def test_tile_groups_cover_the_longitudes():
    assert glc_earth.group_of(-52.0) == "americas"
    assert glc_earth.group_of(10.0) == "europe_africa"
    assert glc_earth.group_of(100.0) == "central_asia"
    assert glc_earth.group_of(150.0) == "australasia"


def test_glc_labels_are_in_the_right_language():
    assert glc.label(210, "en") == "Water body"
    assert glc.label(210, "pt") == "Corpo d'água"
    assert glc.label(11, "en") == "Herbaceous cover cropland"
    assert glc.color(210) == "#2532e4"
    assert glc.band_for_year(2020) == "glc_2020" and glc.source_band(2000) == "b1"
    assert glc.nearest_year("world", 1990) == 2000 and glc.nearest_year("world", 2030) == 2022


def test_class_groups_do_not_overlap():
    groups = [glc.FOREST, glc.WETLAND, glc.GRASS_SHRUB, glc.WATER, glc.BARREN, glc.URBAN, glc.CROPLAND]
    seen: set[int] = set()
    for g in groups:
        assert not (seen & g)
        seen |= g
    assert 210 in glc.WATER and 190 in glc.URBAN


def test_disturbance_bins_start_at_2001():
    assert dcfg.AGE_ORDER[-1].startswith("≥ 25") and len(dcfg.AGE_BINS) == 5
    assert dcfg.LOSS_YEAR_START == 2001 and dcfg.BURN_YEAR_START == 2001
    assert dcfg.CANOPY_YEARS[0] == 2000


@pytest.mark.parametrize("lat, lon, block", [
    (-14.0, -52.0, (-60, -20)), (-30.0, -58.0, (-60, -30)), (0.0, 0.0, (0, 0)),
])
def test_world_block(lat, lon, block):
    assert cb.world_block(lat, lon) == block


def test_no_block_outside_the_built_area():
    assert cb.world_block(85.0, 0.0) is None
    assert cb.world_block(-70.0, 0.0) is None


def test_koppen_labels_cover_the_thirty_classes():
    assert sorted(KOPPEN) == list(range(1, 31)) and KOPPEN[3]["sym"] == "Aw"


def test_buffer_box_covers_the_circle():
    p = geo.point(lat=0.0, lon=0.0)
    w, s, e, n = glc_history.buffer_box(p, 10.0)
    assert w < -0.08 and e > 0.08 and s < -0.08 and n > 0.08


def test_coordinates_outside_the_span_are_refused():
    geo.validate_for_analysis(geo.point(lat=-14.0, lon=-52.0))
    with pytest.raises(geo.CoordinateError):
        geo.validate_for_analysis(geo.point(lat=-75.0, lon=0.0))
    assert geo.region_of(geo.point(lat=50.0, lon=10.0)) == "world"


def test_search_has_no_zip_and_no_country_limit():
    assert geocode.resolve("90210").kind == "lugar"              # a number is a place query, not a US ZIP
    assert geocode.resolve("9.189, 8.668").kind == "coordenada"
    assert geocode._geocoder.countrycodes is None


def test_climate_tab_rows_from_stubbed_readers(monkeypatch):
    row = {"key": "tmean", "unit": "°C", "kind": "abs", "baseline": 27.7, "future": 29.4, "change": 1.7}
    monkeypatch.setattr(cb, "point", lambda lat, lon: {
        "models": 9, "step": 0.5, "hot_day_c": 35.0, "ssp245": [row], "ssp585": [row],
        "koppen": {"base": {"code": 3, "sym": "Aw", "pt": "Savana", "en": "Savannah", "color": "#46aafa"}}})
    monkeypatch.setattr(glc_earth, "terrain", lambda lat, lon: {
        "radius_km": 5.0, "elev_min": 250.0, "elev_mean": 290.0, "elev_max": 400.0, "slope": 2.7})
    rows = climate_rows.build_rows(-14.0, -52.0, "en")
    keys = [r["k"] for r in rows]
    assert "Terrain (Copernicus GLO-30)" in keys and "Climate class (Köppen-Geiger)" in keys
    assert any(r["v"].startswith("27.7 → 29.4") for r in rows)
    assert any(r["v"] == "Aw · Savannah" for r in rows)
    pt = climate_rows.build_rows(-14.0, -52.0, "pt")
    assert any(r["v"] == "Aw · Savana" for r in pt) and any(r["k"] == "Temperatura média" for r in pt)


def test_climate_tab_says_no_data_when_nothing_is_there(monkeypatch):
    monkeypatch.setattr(cb, "point", lambda lat, lon: None)
    monkeypatch.setattr(glc_earth, "terrain", lambda lat, lon: None)
    rows = climate_rows.build_rows(-30.0, -30.0, "en")
    assert len(rows) == 1 and rows[0]["style"] == "muted"
