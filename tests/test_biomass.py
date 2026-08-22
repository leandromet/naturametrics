"""services/biomass.py — the pure-pandas aggregation (no Earth Engine).

biomass_history/full_area_biomass_history need live credentials (the EE
reduce itself); aggregate_biomass is plain pandas and runs offline, same
split as test_landscape_metrics.py.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from naturametrics.services.biomass import (  # noqa: E402
    AGB_YEARS, aggregate_biomass,
)


def _row(radius_km, year, agb_mgha, sd, area_ha):
    return {
        "radius_km": radius_km, "year": year, "agb_mean_mgha": agb_mgha,
        "agb_sd_mgha": sd, "area_ha": area_ha,
        "total_biomass_mg": agb_mgha * area_ha,
    }


def test_years_span_the_two_pre2015_snapshots_and_the_annual_run():
    assert AGB_YEARS[:2] == [2007, 2010]
    assert AGB_YEARS[2:] == list(range(2015, 2023))


def test_aggregate_sums_area_and_mass():
    f1 = pd.DataFrame([_row(1.0, 2020, 100.0, 10.0, 10.0)])  # 1000 Mg
    f2 = pd.DataFrame([_row(1.0, 2020, 50.0, 5.0, 30.0)])    # 1500 Mg
    out = aggregate_biomass([f1, f2])
    row = out.iloc[0]
    assert row["area_ha"] == pytest.approx(40.0)
    assert row["total_biomass_mg"] == pytest.approx(2500.0)


def test_aggregate_recomputes_a_weighted_mean_not_a_plain_average():
    """A small buffer's rate must not count as much as a large one's — the
    plain average of 100 and 50 would be 75, which is wrong here."""
    f1 = pd.DataFrame([_row(1.0, 2020, 100.0, 10.0, 10.0)])
    f2 = pd.DataFrame([_row(1.0, 2020, 50.0, 5.0, 30.0)])
    out = aggregate_biomass([f1, f2])
    row = out.iloc[0]
    assert row["agb_mean_mgha"] == pytest.approx(62.5)  # 2500 / 40
    assert row["agb_mean_mgha"] != pytest.approx(75.0)


def test_aggregate_drops_the_uncertainty_column():
    """agb_sd_mgha does not combine by averaging across independent buffers —
    the aggregate must not carry a column implying it does."""
    f1 = pd.DataFrame([_row(1.0, 2020, 100.0, 10.0, 10.0)])
    out = aggregate_biomass([f1])
    assert "agb_sd_mgha" not in out.columns


def test_aggregate_keeps_radius_and_year_separate():
    f1 = pd.DataFrame([_row(1.0, 2020, 100.0, 10.0, 10.0)])
    f2 = pd.DataFrame([_row(1.0, 2021, 90.0, 9.0, 10.0)])
    f3 = pd.DataFrame([_row(5.0, 2020, 80.0, 8.0, 50.0)])
    out = aggregate_biomass([f1, f2, f3])
    assert len(out) == 3
    assert set(zip(out["radius_km"], out["year"])) == {
        (1.0, 2020), (1.0, 2021), (5.0, 2020),
    }


def test_aggregate_of_nothing_is_an_empty_frame_not_a_crash():
    out = aggregate_biomass([])
    assert out.empty
    assert list(out.columns) == [
        "radius_km", "year", "area_ha", "total_biomass_mg", "agb_mean_mgha",
    ]
