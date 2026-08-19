"""Forest/vegetation age (services/vegetation_age.py, doc/10-forest-age.md estimator E1).

Pure-pandas tests run always; anything that reads the live DSV asset is marked
``ee`` per test, following the convention in test_exports.py.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from naturametrics.config import vegetation_age as fa  # noqa: E402
from naturametrics.services.vegetation_age import (  # noqa: E402
    age_summary, aggregate_forest_age,
)


# --------------------------------------------------------------------------- #
# Config: the censored ceiling and the reporting bins
# --------------------------------------------------------------------------- #

def test_censored_age_equals_the_dsv_record_length():
    """The whole point of the counter design: reaching the ceiling and being
    right-censored are the same condition, and the ceiling is a count of the
    DSV years, not a hand-picked round number ("40")."""
    assert fa.CENSORED_AGE == len(fa.DSV_YEARS)
    assert fa.CENSORED_AGE == fa.DSV_YEAR_END - fa.DSV_YEAR_START + 1


def test_age_bin_edges_cover_every_dated_age_with_no_gap():
    ages_covered = set()
    for lo, hi, _name in fa.AGE_BIN_EDGES:
        ages_covered.update(range(lo, hi + 1))
    assert ages_covered == set(range(1, fa.CENSORED_AGE))


def test_age_bin_places_the_ceiling_in_the_censored_bin_not_a_dated_one():
    assert fa.age_bin(fa.CENSORED_AGE) == fa.censored_label()
    assert fa.age_bin(fa.CENSORED_AGE - 1) != fa.censored_label()


def test_censored_label_names_the_record_start_year():
    assert str(fa.DSV_YEAR_START) in fa.censored_label()
    assert str(fa.CENSORED_AGE) in fa.censored_label()


# --------------------------------------------------------------------------- #
# aggregate_forest_age — same reading as aggregate_histories
# --------------------------------------------------------------------------- #

def _age_row(radius_km, age, area_ha):
    return {
        "radius_km": radius_km, "age": age, "bin": fa.age_bin(age),
        "censored": age >= fa.CENSORED_AGE, "pixels": area_ha * 10, "area_ha": area_ha,
    }


def test_aggregate_forest_age_sums_areas_per_radius_age():
    a = pd.DataFrame.from_records([_age_row(1.0, 5, 10.0), _age_row(1.0, 38, 100.0)])
    b = pd.DataFrame.from_records([_age_row(1.0, 5, 4.0), _age_row(1.0, 38, 50.0)])
    out = aggregate_forest_age([a, b])
    row5 = out[(out["radius_km"] == 1.0) & (out["age"] == 5)].iloc[0]
    row38 = out[(out["radius_km"] == 1.0) & (out["age"] == 38)].iloc[0]
    assert row5["area_ha"] == pytest.approx(14.0)
    assert row38["area_ha"] == pytest.approx(150.0)
    assert bool(row38["censored"]) is True


def test_aggregate_forest_age_keeps_radii_separate():
    a = pd.DataFrame.from_records([_age_row(1.0, 5, 10.0)])
    b = pd.DataFrame.from_records([_age_row(10.0, 5, 10.0)])
    out = aggregate_forest_age([a, b])
    assert set(out["radius_km"]) == {1.0, 10.0}


def test_aggregate_forest_age_of_nothing_is_an_empty_frame_not_a_crash():
    out = aggregate_forest_age([])
    assert out.empty
    assert list(out.columns) == [
        "radius_km", "age", "bin", "censored", "pixels", "area_ha", "color"
    ]


# --------------------------------------------------------------------------- #
# age_summary — doc/10 §5.1: never a bare mean, censored share always surfaced
# --------------------------------------------------------------------------- #

def test_age_summary_median_excludes_censored_area():
    """age_summary's median is a *weighted* median (cumulative area, lower
    convention: the first age whose running share reaches half the dated total)
    — not a plain median of the age values, and never over the censored area."""
    df = pd.DataFrame.from_records([
        _age_row(1.0, 10, 3.0),
        _age_row(1.0, 20, 1.0),
        _age_row(1.0, fa.CENSORED_AGE, 1000.0),  # would swamp a naive mean/median
    ])
    s = age_summary(df, 1.0)
    assert s["median_dated_age"] == pytest.approx(10.0)  # 3 ha at 10 is the majority of the 4 ha dated
    assert s["censored_area_ha"] == pytest.approx(1000.0)
    assert s["censored_pct"] > 99.0


def test_age_summary_of_a_missing_radius_is_empty():
    df = pd.DataFrame.from_records([_age_row(1.0, 10, 1.0)])
    assert age_summary(df, 5.0) == {}


def test_age_summary_of_empty_frame_is_empty():
    assert age_summary(pd.DataFrame(), 1.0) == {}


# --------------------------------------------------------------------------- #
# Earth Engine initialisation — same regression class as test_exports.py
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("entry", ["point_forest_age_series", "buffer_forest_age_histogram"])
def test_forest_age_entry_points_initialise_earth_engine(monkeypatch, entry):
    """A tab left open across a backend restart must not silently skip Earth
    Engine initialisation for the age estimator either — same failure mode
    documented in test_exports.py for the land-cover history entry points."""
    from naturametrics.services import ee_client, vegetation_age
    from naturametrics.services.geo import CoordinateError, point

    calls = []
    monkeypatch.setattr(ee_client, "_initialized", False)
    monkeypatch.setattr(ee_client, "initialize_earth_engine",
                        lambda: calls.append(entry))

    fn = getattr(vegetation_age, entry)
    with pytest.raises(CoordinateError):
        fn(point(lat=48.85, lon=2.35))  # Paris — rejected by validation, no network call

    assert calls == [entry], f"{entry} must call get_ee() before doing anything"


# --------------------------------------------------------------------------- #
# Live Earth Engine — the age counter against real DSV data
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def ee_ready():
    try:
        from naturametrics.services.ee_client import initialize_earth_engine
        initialize_earth_engine()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Earth Engine unavailable: {exc}")
    return True


@pytest.mark.ee
def test_point_series_never_disturbed_reaches_the_censored_ceiling(ee_ready):
    """A pixel that is class 2 every year must count up to exactly CENSORED_AGE
    in the final year — the "no separate censored flag" property the module
    docstring claims."""
    from naturametrics.services.vegetation_age import point_forest_age_series
    from naturametrics.services.geo import point

    df, _prov = point_forest_age_series(point(lat=-11.0, lon=-55.0))
    assert not df.empty
    if (df["class_id"] == 2).all():
        last = df.iloc[-1]
        assert last["age"] == fa.CENSORED_AGE
        assert bool(last["censored"]) is True


@pytest.mark.ee
def test_buffer_histogram_has_no_zero_age_rows(ee_ready):
    """Age 0 means "not vegetated this year" in the counter design, and must
    never appear in the reported distribution — see buffer_forest_age_histogram's
    docstring on why that would misreport "not forest" as "brand-new forest"."""
    from naturametrics.services.vegetation_age import buffer_forest_age_histogram
    from naturametrics.services.geo import point

    df, _prov = buffer_forest_age_histogram(
        point(lat=-9.5, lon=-63.0), radii_km=(1.0, 10.0))
    assert not df.empty
    assert (df["age"] > 0).all()


@pytest.mark.ee
def test_point_series_records_a_disturbance_as_a_reset_to_zero(ee_ready):
    """A pixel with a known clearing must show age drop to 0 in the class-4/6
    year and stay at 0 while classified anthropic afterward — not keep counting
    or carry a stale value forward."""
    from naturametrics.services.vegetation_age import point_forest_age_series
    from naturametrics.services.geo import point

    df, _prov = point_forest_age_series(point(lat=-9.5, lon=-63.0))
    assert not df.empty
    suppressed = df[df["class_id"].isin([4, 6])]
    if not suppressed.empty:
        assert (suppressed["age"] == 0).all()
