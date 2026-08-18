"""Coordinate-order guards.

These exist because a lat/lon swap does not crash — it silently analyses the
wrong place. See naturametrics/services/geo.py for the conventions.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from naturametrics.services.geo import (  # noqa: E402
    CoordinateError, in_brazil, looks_swapped, point, validate_for_analysis,
)

# Machadinho d'Oeste, Rondônia — a real deforestation frontier.
RO = point(lat=-9.85, lon=-62.95)


def test_orders_are_reversed_and_explicit():
    assert RO.to_leaflet() == [-9.85, -62.95]
    assert RO.to_geojson_coords() == [-62.95, -9.85]
    assert RO.to_leaflet() != RO.to_geojson_coords()


def test_geojson_follows_rfc7946():
    assert RO.to_geojson() == {"type": "Point", "coordinates": [-62.95, -9.85]}


def test_brazil_membership():
    assert in_brazil(RO)
    assert not in_brazil(point(lat=-9.85, lon=12.0))       # Angola
    assert not in_brazil(point(lat=48.85, lon=2.35))       # Paris


def test_swap_is_detected():
    """The failure mode this module exists for: Brazilian coords in the wrong order."""
    swapped = point(lat=-62.95, lon=-9.85)   # lands in the South Atlantic
    assert not in_brazil(swapped)
    assert looks_swapped(swapped)
    with pytest.raises(CoordinateError, match="trocad"):
        validate_for_analysis(swapped)


def test_genuinely_outside_brazil_is_not_reported_as_a_swap():
    paris = point(lat=48.85, lon=2.35)
    assert not looks_swapped(paris)
    with pytest.raises(CoordinateError, match="fora do Brasil"):
        validate_for_analysis(paris)


def test_impossible_latitude_rejected_at_construction():
    with pytest.raises(CoordinateError, match="trocad"):
        point(lat=-122.4, lon=37.8)          # San Francisco, reversed


def test_valid_point_passes():
    validate_for_analysis(RO)                # must not raise


def test_key_is_stable_and_precise():
    assert RO.key() == "-9.85000,-62.95000"
    assert point(lat=-9.850001, lon=-62.95).key() == "-9.85000,-62.95000"
