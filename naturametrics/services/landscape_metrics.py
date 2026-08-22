"""Landscape metrics from the latest categorical MapBiomas classification."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..config import mapbiomas as mb
from ..config.settings import (
    BUFFER_RADII_KM, EE_DEFAULT_SCALE_M, EE_MAX_PIXELS, EE_TILE_SCALE,
)
from .buffers import BufferMode, BufferShape, buffer_collection
from .ee_client import get_ee
from .geo import Point, validate_for_analysis
from .provenance import Provenance

logger = logging.getLogger(__name__)


METRIC_COLUMNS = [
    "radius_km", "area_ha", "patches", "patch_density",
    "largest_patch_ha", "largest_patch_pct", "edge_density",
    "shannon", "simpson", "simpson_evenness", "mean_patch_ha",
]


def _metrics_from_properties(props: dict[str, Any], radius: float,
                             pixel_area_m2: float, pixel_scale_m: float) -> dict[str, Any]:
    histogram = props.get("histogram") or {}
    counts = [float(v) for v in histogram.values() if float(v) > 0]
    pixels = sum(counts)
    area_ha = pixels * pixel_area_m2 / 10_000.0
    patches = float(props.get("patches") or 0)
    largest_pixels = float(props.get("largest_patch") or 0)
    edge_fraction = float(props.get("edge_fraction") or 0)
    proportions = [count / pixels for count in counts] if pixels else []
    shannon = -sum(p * __import__("math").log(p) for p in proportions if p > 0)
    simpson = 1.0 - sum(p * p for p in proportions)
    richness = len(proportions)
    evenness = simpson / (1.0 - 1.0 / richness) if richness > 1 else 0.0
    largest_ha = largest_pixels * pixel_area_m2 / 10_000.0
    # Edge pixels are converted to metres of edge per hectare using the native
    # pixel scale. This is a raster edge-density estimate, not a vector perimeter.
    edge_density = edge_fraction * pixels * pixel_scale_m / max(area_ha, 1e-9)
    return {
        "radius_km": float(radius),
        "area_ha": area_ha,
        "patches": patches,
        "patch_density": patches / max(area_ha, 1e-9),
        "largest_patch_ha": largest_ha,
        "largest_patch_pct": largest_ha / max(area_ha, 1e-9) * 100.0,
        "edge_density": edge_density,
        "shannon": shannon,
        "simpson": simpson,
        "simpson_evenness": evenness,
        "mean_patch_ha": area_ha / max(patches, 1.0),
    }


def landscape_metrics(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
    shape: BufferShape = "circle",
    year: int = mb.MAPBIOMAS_YEAR_END,
) -> tuple[pd.DataFrame, Provenance]:
    """Calculate landscape metrics for one point's buffers.

    Patches are contiguous 8-neighbour regions of equal MapBiomas class. NP and
    LPI use Earth Engine connected components; ED is the native-raster boundary
    estimate. Diversity metrics use the class-area histogram. This is deliberately
    single-point: multi-selection aggregation would make patch identity ambiguous.
    """
    import ee
    get_ee()
    validate_for_analysis(p)
    image = ee.Image(mb.MAPBIOMAS_COLLECTIONS[mb.MAPBIOMAS_DEFAULT_COLLECTION]).select(
        mb.band_for_year(year)).rename("class")
    fc = buffer_collection(p, radii_km, mode, shape)
    kernel = ee.Kernel.square(1)
    labels = image.connectedComponents(kernel, 1024).select("labels")
    component_size = image.connectedPixelCount(1024, True).rename("patch_size")
    neighbours = image.neighborhoodToBands(ee.Kernel.plus(1))
    edge = neighbours.neq(image).reduce(ee.Reducer.sum()).gt(0).rename("edge")
    # Select the source bands explicitly so each reducer input is unambiguous.
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
    records = []
    for index, feature in enumerate(hist_info.get("features", [])):
        props = feature.get("properties", {})
        radius = float(props.get("radius_km", sorted(radii_km)[index]))
        patch_props = patch_info["features"][index].get("properties", {})
        largest_props = largest_info["features"][index].get("properties", {})
        edge_props = edge_info["features"][index].get("properties", {})
        area_props = area_info["features"][index].get("properties", {})
        records.append(_metrics_from_properties(
            {"histogram": props.get("histogram"),
             "patches": patch_props.get("countDistinct", patch_props.get("count")),
             "largest_patch": largest_props.get("max"),
             "edge_fraction": edge_props.get("mean")},
            radius, float(area_props.get("mean") or 900.0), EE_DEFAULT_SCALE_M,
        ))
    df = pd.DataFrame.from_records(records, columns=METRIC_COLUMNS)
    prov = Provenance(
        name="landscape_metrics",
        dataset_id=mb.MAPBIOMAS_COLLECTIONS[mb.MAPBIOMAS_DEFAULT_COLLECTION],
        bands=[mb.band_for_year(year)], scale_m=EE_DEFAULT_SCALE_M,
        reducer="frequencyHistogram + connectedComponents + neighbourhood edge",
        pixel_area_basis="mean ee.Image.pixelArea() per buffer",
        max_pixels=EE_MAX_PIXELS, tile_scale=EE_TILE_SCALE,
        geometry=p.to_geojson(),
        extra={"year": year, "buffer_mode": mode, "buffer_shape": shape,
               "radii_km": list(radii_km), "point": str(p),
               "connectivity": "8-neighbour", "edge_basis": "native raster pixels"},
    )
    logger.info("Landscape metrics for %s: %s buffers", p, len(df))
    return df, prov
