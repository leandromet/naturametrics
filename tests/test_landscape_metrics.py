"""services/landscape_metrics.py — the pure-pandas parts (no Earth Engine).

Mirrors test_vegetation_age.py's split: aggregation/diversity math runs
offline; only the EE-backed reduce (landscape_metrics/full_area_landscape_metrics
themselves) would need live credentials, and isn't exercised here.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from naturametrics.services.landscape_metrics import (  # noqa: E402
    METRIC_COLUMNS, aggregate_landscape_metrics, _diversity,
)


def _summary_row(radius_km, area_ha, patches, largest_patch_ha, edge_m,
                  patch_area_sq_ha=None):
    if patch_area_sq_ha is None:
        # No fixture here models the full per-patch size distribution, so this
        # default is an arbitrary stand-in, not a real Σ(patch area²) — tests
        # that care about its exact value pass patch_area_sq_ha explicitly
        # (test_aggregate_sums_patch_area_sq_and_recomputes_meff).
        patch_area_sq_ha = largest_patch_ha ** 2
    return {
        "radius_km": radius_km, "area_ha": area_ha, "patches": patches,
        "patch_density": patches / area_ha, "largest_patch_ha": largest_patch_ha,
        "largest_patch_pct": largest_patch_ha / area_ha * 100.0, "edge_m": edge_m,
        "edge_density": edge_m / area_ha, "mean_patch_ha": area_ha / patches,
        "patch_area_sq_ha": patch_area_sq_ha, "meff_ha": patch_area_sq_ha / area_ha,
        # Per-point diversity is discarded by the aggregator — placeholder
        # values here to prove that, not values the test depends on.
        "shannon": -1.0, "simpson": -1.0, "simpson_evenness": -1.0,
    }


def _hist_row(radius_km, class_id, area_ha):
    return {"radius_km": radius_km, "class_id": class_id,
            "pixels": area_ha * 10, "area_ha": area_ha}


def test_diversity_of_a_single_class_is_zero():
    hist = pd.DataFrame([_hist_row(1.0, 3, 10.0)])
    d = _diversity(hist, 1.0)
    assert d["shannon"] == pytest.approx(0.0)
    assert d["simpson"] == pytest.approx(0.0)
    assert d["simpson_evenness"] == pytest.approx(0.0)


def test_diversity_of_an_even_two_class_split_is_maximal_evenness():
    hist = pd.DataFrame([_hist_row(1.0, 3, 5.0), _hist_row(1.0, 15, 5.0)])
    d = _diversity(hist, 1.0)
    assert d["shannon"] == pytest.approx(0.6931, abs=1e-3)  # ln(2)
    assert d["simpson"] == pytest.approx(0.5)
    assert d["simpson_evenness"] == pytest.approx(1.0)  # perfectly even


def test_diversity_of_an_empty_histogram_is_zero_not_a_crash():
    empty = pd.DataFrame(columns=["radius_km", "class_id", "pixels", "area_ha"])
    d = _diversity(empty, 1.0)
    assert d == {"shannon": 0.0, "simpson": 0.0, "simpson_evenness": 0.0}


def test_aggregate_sums_area_patches_and_edge_length():
    s1 = pd.DataFrame([_summary_row(1.0, 10.0, 2, 6.0, 100.0)])
    s2 = pd.DataFrame([_summary_row(1.0, 5.0, 1, 5.0, 50.0)])
    h1 = pd.DataFrame([_hist_row(1.0, 3, 9.0), _hist_row(1.0, 15, 1.0)])
    h2 = pd.DataFrame([_hist_row(1.0, 3, 5.0)])

    out = aggregate_landscape_metrics([s1, s2], [h1, h2])
    row = out.iloc[0]
    assert list(out.columns) == METRIC_COLUMNS
    assert row["area_ha"] == pytest.approx(15.0)
    assert row["patches"] == pytest.approx(3.0)
    assert row["edge_m"] == pytest.approx(150.0)
    assert row["edge_density"] == pytest.approx(10.0)  # 150 / 15


def test_aggregate_sums_patch_area_sq_and_recomputes_meff():
    """meff_ha (effective mesh size) must be recomputed from the summed
    Σ(patch area²) term, not summed or averaged directly itself — same
    reasoning as edge_density/patch_density/mean_patch_ha above it."""
    s1 = pd.DataFrame([_summary_row(1.0, 10.0, 2, 6.0, 100.0, patch_area_sq_ha=40.0)])
    s2 = pd.DataFrame([_summary_row(1.0, 5.0, 1, 5.0, 50.0, patch_area_sq_ha=25.0)])
    out = aggregate_landscape_metrics([s1, s2], [])
    row = out.iloc[0]
    assert row["patch_area_sq_ha"] == pytest.approx(65.0)
    assert row["meff_ha"] == pytest.approx(65.0 / 15.0)


def test_aggregate_takes_the_max_largest_patch_not_a_sum():
    """The biggest single patch found in any contributing buffer — summing or
    averaging "the largest patch" across separate landscapes would not
    describe anything real."""
    s1 = pd.DataFrame([_summary_row(1.0, 10.0, 2, 6.0, 100.0)])
    s2 = pd.DataFrame([_summary_row(1.0, 5.0, 1, 5.0, 50.0)])
    out = aggregate_landscape_metrics([s1, s2], [])
    assert out.iloc[0]["largest_patch_ha"] == pytest.approx(6.0)


def test_aggregate_recomputes_diversity_from_pooled_classes_not_average():
    """Diversity must come from the summed class-area histogram, not from
    averaging each point's own (discarded) shannon/simpson."""
    s1 = pd.DataFrame([_summary_row(1.0, 9.0, 1, 9.0, 10.0)])
    s2 = pd.DataFrame([_summary_row(1.0, 5.0, 1, 5.0, 10.0)])
    h1 = pd.DataFrame([_hist_row(1.0, 3, 9.0)])       # all one class
    h2 = pd.DataFrame([_hist_row(1.0, 15, 5.0)])       # a different single class

    out = aggregate_landscape_metrics([s1, s2], [h1, h2])
    pooled = pd.concat([h1, h2], ignore_index=True)
    expected = _diversity(pooled, 1.0)
    row = out.iloc[0]
    # Pooled: two classes, 9 vs 5 ha — real diversity, not the -1.0 placeholder
    # each per-point summary row carried (and not zero, as either input alone
    # would give).
    assert row["shannon"] == pytest.approx(expected["shannon"])
    assert row["shannon"] > 0.0
    assert row["shannon"] != -1.0


def test_aggregate_of_nothing_is_an_empty_frame_not_a_crash():
    out = aggregate_landscape_metrics([], [])
    assert out.empty
    assert list(out.columns) == METRIC_COLUMNS


def test_aggregate_keeps_radii_separate():
    s1 = pd.DataFrame([_summary_row(1.0, 10.0, 2, 6.0, 100.0)])
    s2 = pd.DataFrame([_summary_row(5.0, 20.0, 3, 10.0, 200.0)])
    out = aggregate_landscape_metrics([s1, s2], [])
    assert set(out["radius_km"]) == {1.0, 5.0}
