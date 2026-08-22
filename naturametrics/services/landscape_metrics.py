"""Landscape metrics from the latest categorical MapBiomas classification."""

from __future__ import annotations

import logging
import math
from typing import Any

import pandas as pd

from ..config import mapbiomas as mb
from ..config.settings import (
    BUFFER_RADII_KM, EE_DEFAULT_SCALE_M, EE_MAX_PIXELS, EE_TILE_SCALE,
)
from .buffers import (
    BufferMode, BufferShape, buffer_collection,
    full_area_bbox, full_area_collection, full_area_geojson,
)
from .ee_client import get_ee
from .geo import Point, validate_for_analysis
from .provenance import Provenance

logger = logging.getLogger(__name__)


#: The per-radius summary — one row per buffer (or, in full-area mode, one row
#: for the single outer box). Diversity indices (shannon/simpson/
#: simpson_evenness) are always computed from HISTOGRAM_COLUMNS by
#: :func:`_diversity`, in :func:`_landscape_metrics_from_collection` for a
#: single point/full-area and in :func:`aggregate_landscape_metrics` for a
#: multi-selection sum — the *same* formula in both cases, applied to whatever
#: histogram is at hand, rather than a per-point value that a sum would then
#: have to (wrongly) average.
METRIC_COLUMNS = [
    "radius_km", "area_ha", "patches", "patch_density",
    "largest_patch_ha", "largest_patch_pct", "edge_m", "edge_density",
    "mean_patch_ha", "shannon", "simpson", "simpson_evenness",
]

#: The per-class histogram behind the summary above — same long format as
#: mapbiomas_history.land_cover_history, minus the year axis (this reads one
#: classification year, not a 40-year series).
HISTOGRAM_COLUMNS = ["radius_km", "class_id", "pixels", "area_ha"]


def _diversity(hist_df: pd.DataFrame, radius_km: float) -> dict[str, float]:
    """Shannon / Gini-Simpson / Simpson's evenness for one radius's class-area
    histogram. The one formula, used identically for a single point's own
    classes and for several points' classes already pooled — see
    :func:`aggregate_landscape_metrics`.
    """
    sub = hist_df[hist_df["radius_km"] == radius_km] if not hist_df.empty else hist_df
    total = float(sub["area_ha"].sum()) if not sub.empty else 0.0
    if total <= 0:
        return {"shannon": 0.0, "simpson": 0.0, "simpson_evenness": 0.0}
    proportions = (sub["area_ha"] / total).to_numpy()
    shannon = -sum(p * math.log(p) for p in proportions if p > 0)
    simpson = 1.0 - float(sum(p * p for p in proportions))
    richness = int((proportions > 0).sum())
    evenness = simpson / (1.0 - 1.0 / richness) if richness > 1 else 0.0
    return {"shannon": shannon, "simpson": simpson, "simpson_evenness": evenness}


def _summary_from_properties(
    props: dict[str, Any], radius: float, pixel_area_m2: float, pixel_scale_m: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """One radius's summary row, plus its class histogram as long-format records."""
    histogram = props.get("histogram") or {}
    counts = {int(float(k)): float(v) for k, v in histogram.items() if float(v) > 0}
    pixels = sum(counts.values())
    area_ha = pixels * pixel_area_m2 / 10_000.0
    patches = float(props.get("patches") or 0)
    largest_pixels = float(props.get("largest_patch") or 0)
    edge_fraction = float(props.get("edge_fraction") or 0)
    largest_ha = largest_pixels * pixel_area_m2 / 10_000.0
    # Edge pixels converted to metres of edge via the native pixel scale — a
    # raster edge-density estimate, not a vector perimeter (kept as a raw
    # length, edge_m, alongside the ratio, so a multi-selection sum can add
    # lengths and areas separately and only divide once, at the end).
    edge_m = edge_fraction * pixels * pixel_scale_m
    summary = {
        "radius_km": float(radius),
        "area_ha": area_ha,
        "patches": patches,
        "patch_density": patches / max(area_ha, 1e-9),
        "largest_patch_ha": largest_ha,
        "largest_patch_pct": largest_ha / max(area_ha, 1e-9) * 100.0,
        "edge_m": edge_m,
        "edge_density": edge_m / max(area_ha, 1e-9),
        "mean_patch_ha": area_ha / max(patches, 1.0),
    }
    hist_records = [
        {"radius_km": float(radius), "class_id": class_id,
         "pixels": count, "area_ha": count * pixel_area_m2 / 10_000.0}
        for class_id, count in counts.items()
    ]
    return summary, hist_records


def _landscape_metrics_from_collection(
    fc: Any,
    *,
    geometry: dict[str, Any] | None,
    point_label: str,
    mode: str,
    shape: str,
    radii_km: tuple[float, ...],
    year: int,
) -> tuple[pd.DataFrame, pd.DataFrame, Provenance]:
    """Shared reduce/parsing body behind :func:`landscape_metrics` and
    :func:`full_area_landscape_metrics` — generic over where ``fc``'s geometry
    came from, same split as mapbiomas_history._history_from_collection.
    """
    import ee

    image = ee.Image(mb.MAPBIOMAS_COLLECTIONS[mb.MAPBIOMAS_DEFAULT_COLLECTION]).select(
        mb.band_for_year(year)).rename("class")
    kernel = ee.Kernel.square(1)
    labels = image.connectedComponents(kernel, 1024).select("labels")
    component_size = image.connectedPixelCount(1024, True).rename("patch_size")
    neighbours = image.neighborhoodToBands(ee.Kernel.plus(1))
    edge = neighbours.neq(image).reduce(ee.Reducer.sum()).gt(0).rename("edge")

    reduced = image.reduceRegions(collection=fc, reducer=ee.Reducer.frequencyHistogram(),
                                  scale=EE_DEFAULT_SCALE_M, tileScale=EE_TILE_SCALE)
    patch_reduced = labels.reduceRegions(collection=fc, reducer=ee.Reducer.countDistinct(),
                                         scale=EE_DEFAULT_SCALE_M, tileScale=EE_TILE_SCALE)
    largest_reduced = component_size.reduceRegions(collection=fc, reducer=ee.Reducer.max(),
                                                    scale=EE_DEFAULT_SCALE_M, tileScale=EE_TILE_SCALE)
    edge_reduced = edge.reduceRegions(collection=fc, reducer=ee.Reducer.mean(),
                                      scale=EE_DEFAULT_SCALE_M, tileScale=EE_TILE_SCALE)
    area_reduced = ee.Image.pixelArea().reduceRegions(
        collection=fc, reducer=ee.Reducer.mean(),
        scale=EE_DEFAULT_SCALE_M, tileScale=EE_TILE_SCALE)

    hist_info = reduced.getInfo()
    patch_info = patch_reduced.getInfo()
    largest_info = largest_reduced.getInfo()
    edge_info = edge_reduced.getInfo()
    area_info = area_reduced.getInfo()

    summaries: list[dict[str, Any]] = []
    hist_records: list[dict[str, Any]] = []
    for index, feature in enumerate(hist_info.get("features", [])):
        props = feature.get("properties", {})
        radius = float(props.get("radius_km", sorted(radii_km)[index]))
        patch_props = patch_info["features"][index].get("properties", {})
        largest_props = largest_info["features"][index].get("properties", {})
        edge_props = edge_info["features"][index].get("properties", {})
        area_props = area_info["features"][index].get("properties", {})
        summary, records = _summary_from_properties(
            {"histogram": props.get("histogram"),
             "patches": patch_props.get("countDistinct", patch_props.get("count")),
             "largest_patch": largest_props.get("max"),
             "edge_fraction": edge_props.get("mean")},
            radius, float(area_props.get("mean") or 900.0), EE_DEFAULT_SCALE_M,
        )
        summaries.append(summary)
        hist_records.extend(records)

    summary_cols = [c for c in METRIC_COLUMNS if c not in ("shannon", "simpson", "simpson_evenness")]
    summary_df = pd.DataFrame.from_records(summaries, columns=summary_cols)
    hist_df = pd.DataFrame.from_records(hist_records, columns=HISTOGRAM_COLUMNS)

    # Diversity is computed here — not carried in `summaries` above — so that
    # a single point, a full-area box and a multi-selection sum
    # (aggregate_landscape_metrics) all get it from the exact same formula
    # applied to whatever histogram is at hand, rather than three subtly
    # different code paths.
    if not summary_df.empty:
        diversity = [_diversity(hist_df, r) for r in summary_df["radius_km"]]
        summary_df["shannon"] = [d["shannon"] for d in diversity]
        summary_df["simpson"] = [d["simpson"] for d in diversity]
        summary_df["simpson_evenness"] = [d["simpson_evenness"] for d in diversity]
    else:
        for col in ("shannon", "simpson", "simpson_evenness"):
            summary_df[col] = pd.Series(dtype="float64")
    summary_df = summary_df[METRIC_COLUMNS]

    prov = Provenance(
        name="landscape_metrics",
        dataset_id=mb.MAPBIOMAS_COLLECTIONS[mb.MAPBIOMAS_DEFAULT_COLLECTION],
        bands=[mb.band_for_year(year)], scale_m=EE_DEFAULT_SCALE_M,
        reducer="frequencyHistogram + connectedComponents + neighbourhood edge",
        pixel_area_basis="mean ee.Image.pixelArea() per buffer",
        max_pixels=EE_MAX_PIXELS, tile_scale=EE_TILE_SCALE,
        geometry=geometry,
        extra={"year": year, "buffer_mode": mode, "buffer_shape": shape,
               "radii_km": list(radii_km), "point": point_label,
               "connectivity": "8-neighbour", "edge_basis": "native raster pixels",
               # connectedComponents/connectedPixelCount mask/cap at this many
               # pixels (~92 ha) — a patch bigger than that reads as truncated,
               # which is common for intact-forest buffers above ~1 km. Kept in
               # provenance rather than silently accepted, per constraint C6.
               "patch_size_cap_pixels": 1024},
    )
    logger.info("Landscape metrics for %s: %s radii, %s classes", point_label,
                len(summary_df), len(hist_df))
    return summary_df, hist_df, prov


def landscape_metrics(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
    shape: BufferShape = "circle",
    year: int = mb.MAPBIOMAS_YEAR_END,
) -> tuple[pd.DataFrame, pd.DataFrame, Provenance]:
    """Landscape metrics for one point's buffers.

    Patches are contiguous 8-neighbour regions of equal MapBiomas class. NP and
    LPI use Earth Engine connected components; ED is the native-raster boundary
    estimate. Diversity metrics (shannon/simpson/simpson_evenness) are computed
    from the returned histogram by :func:`_diversity`, not carried as columns
    here — see :func:`aggregate_landscape_metrics` for why.
    """
    get_ee()
    validate_for_analysis(p)
    fc = buffer_collection(p, radii_km, mode, shape)
    return _landscape_metrics_from_collection(
        fc, geometry=p.to_geojson(), point_label=str(p), mode=mode, shape=shape,
        radii_km=radii_km, year=year,
    )


def full_area_landscape_metrics(
    points: list[Point],
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    shape: BufferShape = "circle",
    year: int = mb.MAPBIOMAS_YEAR_END,
) -> tuple[pd.DataFrame, pd.DataFrame, Provenance]:
    """Landscape metrics over the single bounding box enclosing every selected
    point's outer buffer.

    Unlike a per-point sum, patch identity here is unambiguous: there is
    exactly one region, so NP/LPI/ED mean exactly what they mean for a single
    point — this is the "área total" reading of landscape metrics, not an
    aggregation across separate landscapes.
    """
    get_ee()
    bbox = full_area_bbox(points, radii_km, shape)
    fc = full_area_collection(points, radii_km, shape, bbox=bbox)
    summary_df, hist_df, prov = _landscape_metrics_from_collection(
        fc, geometry=full_area_geojson(points, radii_km, shape, bbox=bbox),
        point_label=f"{len(points)} points (full area)", mode="full_area",
        shape=shape, radii_km=radii_km, year=year,
    )
    prov.extra["n_points"] = len(points)
    prov.extra["outer_radius_km"] = max(radii_km)
    prov.extra["bbox_wgs84"] = list(bbox)
    return summary_df, hist_df, prov


def aggregate_landscape_metrics(
    summaries: list[pd.DataFrame], histograms: list[pd.DataFrame],
) -> pd.DataFrame:
    """Sum several conglomerados' landscape metrics into one, per radius.

    ``area_ha``, ``patches`` and ``edge_m`` **add** — the same "sum over
    sampling units, overlap counted in each" reading ``aggregate_histories``
    gives the land-cover sum. ``largest_patch_ha`` takes the **max** across
    points (the single biggest patch found in any contributing buffer — a sum
    or average of "the largest" would not describe anything real). Shannon/
    Simpson/evenness are **recomputed from the pooled class-area histogram**,
    not averaged: an average of diversity indices is not the diversity of the
    combined landscape, the same reasoning that keeps area_pct out of the
    per-point land-cover frames and recomputes it after summing.
    """
    summaries = [s for s in summaries if s is not None and not s.empty]
    histograms = [h for h in histograms if h is not None and not h.empty]
    if not summaries:
        return pd.DataFrame(columns=METRIC_COLUMNS)

    combined_summary = pd.concat(summaries, ignore_index=True)
    combined_hist = (pd.concat(histograms, ignore_index=True) if histograms
                     else pd.DataFrame(columns=HISTOGRAM_COLUMNS))

    agg = combined_summary.groupby("radius_km", as_index=False).agg(
        area_ha=("area_ha", "sum"),
        patches=("patches", "sum"),
        edge_m=("edge_m", "sum"),
        largest_patch_ha=("largest_patch_ha", "max"),
    )
    safe_area = agg["area_ha"].clip(lower=1e-9)
    agg["patch_density"] = agg["patches"] / safe_area
    agg["largest_patch_pct"] = agg["largest_patch_ha"] / safe_area * 100.0
    agg["edge_density"] = agg["edge_m"] / safe_area
    agg["mean_patch_ha"] = agg["area_ha"] / agg["patches"].clip(lower=1.0)

    diversity = [_diversity(combined_hist, r) for r in agg["radius_km"]]
    agg["shannon"] = [d["shannon"] for d in diversity]
    agg["simpson"] = [d["simpson"] for d in diversity]
    agg["simpson_evenness"] = [d["simpson_evenness"] for d in diversity]

    return agg[METRIC_COLUMNS].sort_values("radius_km").reset_index(drop=True)
