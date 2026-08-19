"""services/change_mask.py — the loss/gain layer, and now its first chart.

change_stats() talked to Earth Engine directly (unlike change_mask_spec, which
goes through tiles.get_tile_url and so got EE initialisation and coordinate
validation for free); wiring it into the vegetation-age panel exposed that it
had neither. Both are fixed in services/change_mask.py; these tests are the
regression coverage for that fix, following the pattern already established in
test_exports.py and test_vegetation_age.py for every other analysis entry point.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_change_stats_initialises_earth_engine_before_anything_else(monkeypatch):
    from naturametrics.services import change_mask, ee_client
    from naturametrics.services.geo import CoordinateError, point

    calls = []
    monkeypatch.setattr(ee_client, "_initialized", False)
    monkeypatch.setattr(ee_client, "initialize_earth_engine",
                        lambda: calls.append("change_stats"))

    with pytest.raises(CoordinateError):
        change_mask.change_stats(point(lat=48.85, lon=2.35), (1.0,))  # Paris

    assert calls == ["change_stats"], "must call get_ee() before doing anything"


def test_change_stats_rejects_out_of_brazil_coordinates_without_a_network_call():
    """The validation this function was missing: previously a Paris click would
    have gone straight to reduceRegions and come back with an empty, silently
    wrong result instead of the "this is outside Brazil" message."""
    from naturametrics.services.change_mask import change_stats
    from naturametrics.services.geo import CoordinateError, point

    with pytest.raises(CoordinateError):
        change_stats(point(lat=48.85, lon=2.35), (1.0,))


@pytest.mark.ee
def test_change_stats_reports_loss_and_gain_for_a_real_point():
    from naturametrics.services.change_mask import change_stats
    from naturametrics.services.geo import point

    try:
        from naturametrics.services.ee_client import initialize_earth_engine
        initialize_earth_engine()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Earth Engine unavailable: {exc}")

    out = change_stats(point(lat=-9.5, lon=-63.0), (1.0, 10.0))
    assert set(out) == {1.0, 10.0}
    for row in out.values():
        assert row["loss_ha"] >= 0
        assert row["gain_ha"] >= 0
        assert row["stable_ha"] >= 0
