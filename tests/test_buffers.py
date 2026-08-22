"""services/buffers.py — the local (non-EE) buffer geometry.

full_area_bbox and friends are plain pyproj/shapely, no Earth Engine round-trip,
so they run offline like the rest of this file's tests.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from naturametrics.services.buffers import full_area_bbox, full_area_geojson  # noqa: E402
from naturametrics.services.geo import point  # noqa: E402


def test_full_area_bbox_of_one_point_is_centred_on_it():
    p = point(lat=-15.0, lon=-55.0)
    west, south, east, north = full_area_bbox([p], (1.0,), "circle")
    assert (west + east) / 2 == pytest.approx(p.lon, abs=1e-6)
    assert (south + north) / 2 == pytest.approx(p.lat, abs=1e-6)
    # A 1 km radius is roughly 0.009 degrees at this latitude either side.
    assert east - west == pytest.approx(0.018, abs=0.002)


def test_full_area_bbox_of_two_points_is_the_union_not_either_alone():
    p1 = point(lat=-15.0, lon=-55.0)
    p2 = point(lat=-15.0, lon=-54.9)  # ~11 km east, well outside a 1 km buffer
    solo = full_area_bbox([p1], (1.0,), "circle")
    combo = full_area_bbox([p1, p2], (1.0,), "circle")
    assert combo[2] > solo[2]  # east edge extends to cover p2
    assert combo[0] == pytest.approx(solo[0], abs=1e-6)  # west edge unchanged


def test_full_area_bbox_side_doubles_for_square_same_as_circle_radius():
    """Squares circumscribe the same-radius circle (side = 2r, per the map's
    buffer-shape design) — the bounding box must be wider for a square than a
    circle at the same nominal radius, not the same width."""
    p = point(lat=-15.0, lon=-55.0)
    circle = full_area_bbox([p], (1.0,), "circle")
    square = full_area_bbox([p], (1.0,), "square")
    assert (square[2] - square[0]) > (circle[2] - circle[0])


def test_full_area_bbox_uses_only_the_outer_radius():
    """A box per smaller radius would nest entirely inside the outer one and
    add nothing — full_area_bbox must ignore every radius but the largest."""
    p = point(lat=-15.0, lon=-55.0)
    outer_only = full_area_bbox([p], (10.0,), "circle")
    with_smaller = full_area_bbox([p], (1.0, 2.0, 5.0, 10.0), "circle")
    assert with_smaller == pytest.approx(outer_only)


def test_full_area_geojson_rectangle_matches_the_bbox():
    p = point(lat=-15.0, lon=-55.0)
    bbox = full_area_bbox([p], (2.0,), "circle")
    gj = full_area_geojson([p], (2.0,), "circle", bbox=bbox)
    assert len(gj["features"]) == 1
    feature = gj["features"][0]
    assert feature["properties"]["radius_km"] == 2.0
    west, south, east, north = bbox
    ring = feature["geometry"]["coordinates"][0]
    lons = [c[0] for c in ring]
    lats = [c[1] for c in ring]
    assert min(lons) == pytest.approx(west)
    assert max(lons) == pytest.approx(east)
    assert min(lats) == pytest.approx(south)
    assert max(lats) == pytest.approx(north)


def test_full_area_geojson_uses_the_outer_radius_label():
    p = point(lat=-15.0, lon=-55.0)
    gj = full_area_geojson([p], (1.0, 2.0, 10.0), "circle")
    assert gj["features"][0]["properties"]["radius_km"] == 10.0
    assert gj["features"][0]["properties"]["label"] == "10 km"
