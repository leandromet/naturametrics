"""Does the fast area method agree with the exact one? (decision D3)

``land_cover_history`` computes area as ``pixel_count × mean_pixelArea``, which
takes one cheap extra call and stays a single batched round-trip for the whole
40-year × 4-buffer matrix. The textbook-exact method is a per-class **grouped**
reducer over ``ee.Image.pixelArea()``, which cannot be batched across bands —
it costs one call per year per buffer.

These tests check the fast method against the exact one, and against the flat
0.09 ha/pixel assumption it replaces. They hit Earth Engine, so they are marked
``ee`` and skipped when credentials are unavailable.

Run with:  pytest tests/test_area_accounting.py -m ee
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytestmark = pytest.mark.ee


@pytest.fixture(scope="module")
def ee_ready():
    try:
        from naturametrics.services.ee_client import initialize_earth_engine
        initialize_earth_engine()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Earth Engine unavailable: {exc}")
    return True


def _exact_area_by_class(p, radius_km, year):
    """Grouped reducer over pixelArea — the method we are checking against."""
    import ee

    from naturametrics.config import mapbiomas as mb

    geom = p.to_ee_point().buffer(radius_km * 1000.0)
    img = ee.Image(mb.MAPBIOMAS_COLLECTIONS[mb.MAPBIOMAS_DEFAULT_COLLECTION])
    grouped = (
        ee.Image.pixelArea()
        .addBands(img.select(mb.band_for_year(year)))
        .reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName="class_id"),
            geometry=geom,
            scale=30,
            maxPixels=int(1e10),
            tileScale=4,
        )
        .getInfo()
    )
    return {int(g["class_id"]): g["sum"] / 10_000.0 for g in grouped["groups"]}


@pytest.mark.parametrize("radius_km", [1.0, 5.0])
def test_fast_area_matches_grouped_reducer(ee_ready, radius_km):
    """Agreement must be well under classification error — we require <0.5%."""
    from naturametrics.services.geo import point
    from naturametrics.services.mapbiomas_history import land_cover_history

    p = point(lat=-9.85, lon=-62.95)
    year = 2024

    df, _ = land_cover_history(p, radii_km=(radius_km,), years=[year])
    fast = df.set_index("class_id")["area_ha"].to_dict()
    exact = _exact_area_by_class(p, radius_km, year)

    assert set(fast) == set(exact), "class sets differ between the two methods"

    total_exact = sum(exact.values())
    for class_id, exact_ha in exact.items():
        if exact_ha < total_exact * 0.01:
            continue  # ignore slivers: quantisation dominates there
        rel = abs(fast[class_id] - exact_ha) / exact_ha
        assert rel < 0.005, (
            f"class {class_id}: fast {fast[class_id]:.2f} ha vs "
            f"exact {exact_ha:.2f} ha ({rel:.3%})"
        )

    rel_total = abs(sum(fast.values()) - total_exact) / total_exact
    assert rel_total < 0.005, f"totals differ by {rel_total:.3%}"


def test_flat_pixel_assumption_would_be_wrong(ee_ready):
    """The 0.09 ha/pixel shortcut D3 rejected is measurably biased.

    Guards the reason for the decision, not just its implementation: if someone
    later 'simplifies' back to a flat constant, this fails and says why.
    """
    from naturametrics.services.geo import point
    from naturametrics.services.mapbiomas_history import land_cover_history

    p = point(lat=-9.85, lon=-62.95)
    df, prov = land_cover_history(p, radii_km=(5.0,), years=[2024])

    mean_px = float(prov.extra["mean_pixel_area_m2"]["5"])
    assert 850 < mean_px < 900, f"unexpected mean pixel area {mean_px} m²"

    flat_total = df["pixels"].sum() * 0.09
    measured_total = df["area_ha"].sum()
    bias = (flat_total - measured_total) / measured_total
    assert bias > 0.015, (
        f"flat 0.09 ha/pixel over-states area by only {bias:.2%} here; the "
        f"decision assumed a latitude-dependent bias worth correcting"
    )


def test_single_year_query_returns_data(ee_ready):
    """Regression: a one-band reduceRegions names its output 'histogram'.

    Earth Engine names the output property per band when several bands are
    selected, but uses the reducer's own name when there is exactly one. A parser
    keyed only on 'classification_*' returns an EMPTY frame for a single-year
    query — and empty, not an error, so it looks like "no data here".
    """
    from naturametrics.services.geo import point
    from naturametrics.services.mapbiomas_history import land_cover_history

    p = point(lat=-9.85, lon=-62.95)

    one, _ = land_cover_history(p, radii_km=(2.0,), years=[2024])
    assert not one.empty, "single-year query returned no rows"
    assert set(one["year"].unique()) == {2024}

    two, _ = land_cover_history(p, radii_km=(2.0,), years=[2023, 2024])
    assert set(two["year"].unique()) == {2023, 2024}

    # The same year through both code paths must agree.
    a = one[one.year == 2024]["area_ha"].sum()
    b = two[two.year == 2024]["area_ha"].sum()
    assert abs(a - b) / b < 1e-6
