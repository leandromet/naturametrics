"""services/change_mask.py — the loss/gain layer, and now its first chart + export.

change_stats() talked to Earth Engine directly (unlike change_mask_spec, which
goes through tiles.get_tile_url and so got EE initialisation and coordinate
validation for free); wiring it into the vegetation-age panel exposed that it
had neither, and also that it returned bare data with no Provenance — the one
analysis entry point in the app that didn't, which was fine as long as nothing
downstream needed to cite it and stopped being fine the moment an export tab
did (constraint C6, doc/01-premises.md). All three are fixed in
services/change_mask.py; these tests are the regression coverage, following the
pattern already established in test_exports.py and test_vegetation_age.py for
every other analysis entry point.
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

    out, prov = change_stats(point(lat=-9.5, lon=-63.0), (1.0, 10.0))
    assert set(out) == {1.0, 10.0}
    for row in out.values():
        assert row["loss_ha"] >= 0
        assert row["gain_ha"] >= 0
        assert row["stable_ha"] >= 0
    assert prov.name == "change_stats"
    assert prov.dataset_id


@pytest.mark.ee
def test_change_stats_provenance_names_the_baseline_and_current_years():
    """C6: the sheet this feeds must be able to say which years it compares."""
    from naturametrics.services.change_mask import FOREST_CODE_BASELINE_YEAR, change_stats
    from naturametrics.services.geo import point

    try:
        from naturametrics.services.ee_client import initialize_earth_engine
        initialize_earth_engine()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Earth Engine unavailable: {exc}")

    _out, prov = change_stats(point(lat=-9.5, lon=-63.0), (1.0,))
    assert prov.extra["year_from"] == FOREST_CODE_BASELINE_YEAR
    assert prov.extra["year_to"] > FOREST_CODE_BASELINE_YEAR
