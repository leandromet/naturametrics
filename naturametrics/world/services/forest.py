"""Forest change (Hansen GFC) over the buffers, USA page.

Hansen is global, so it answers everywhere in the lower 48. Unlike the Canada page
there is no stand-age half: NTEMS is Canadian.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ...config.settings import (
    BUFFER_RADII_KM, EE_DEFAULT_SCALE_M, EE_MAX_PIXELS, EE_TILE_SCALE,
)
from ...services.buffers import BufferMode, buffer_collection, disc_area_ha
from ...services.ee_client import get_ee
from ...services.provenance import Provenance
from ..config import forest as fc_cfg
from .geo import Point, validate_for_analysis

logger = logging.getLogger(__name__)


def hansen_image():
    import ee
    return ee.Image(fc_cfg.HANSEN_GFC_DATASET)


# --------------------------------------------------------------------------- #
# Hansen forest change
# --------------------------------------------------------------------------- #

def change_stats(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
    treecover_threshold: int | None = None,
) -> tuple[dict[str, dict[str, float]], Provenance]:
    """Hansen tree-cover loss and gain per buffer, 2001–2025.

    Returns ``{radius: {loss_ha, gain_ha, forest2000_ha}}``.

    ``gain`` is a single flag over the whole record, not a dated series, so it
    comes back as one total per buffer while loss also carries a year — a
    property of the product, and the reason the chart pairs a dated loss series
    with an undated gain bar.
    """
    import ee

    get_ee()
    validate_for_analysis(p)

    threshold = (fc_cfg.HANSEN_TREECOVER_THRESHOLD
                 if treecover_threshold is None else treecover_threshold)
    fc = buffer_collection(p, radii_km, mode)
    gfc = hansen_image()

    forest2000 = gfc.select("treecover2000").gte(threshold)
    area_ha = ee.Image.pixelArea().divide(10_000.0)
    loss_mask = gfc.select("loss").eq(1).And(forest2000)
    # Loss restricted to the years gain actually covers (2001–2012), so the two
    # can be netted honestly. Without this the panel would subtract a 13-year
    # gain from a 25-year loss and call the result a net.
    loss_in_gain_window = loss_mask.And(
        gfc.select("lossyear").lte(fc_cfg.HANSEN_GAIN_WINDOW_LOSS_CODE))
    stack = (
        area_ha.updateMask(loss_mask).rename("loss_ha")
        .addBands(area_ha.updateMask(gfc.select("gain").eq(1)).rename("gain_ha"))
        .addBands(area_ha.updateMask(loss_in_gain_window).rename("loss_gain_window_ha"))
        .addBands(area_ha.updateMask(forest2000).rename("forest2000_ha"))
    )

    prov = Provenance(
        name="world_forest_change",
        dataset_id=fc_cfg.HANSEN_GFC_DATASET,
        bands=["treecover2000", "loss", "lossyear", "gain"],
        scale_m=EE_DEFAULT_SCALE_M,
        reducer="sum",
        pixel_area_basis="ee.Image.pixelArea() per pixel",
        max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE,
        geometry=p.to_geojson(),
        extra={
            "treecover_threshold_pct": threshold,
            "loss_year_range": f"{fc_cfg.HANSEN_LOSS_YEAR_START}–"
                               f"{fc_cfg.HANSEN_LOSS_YEAR_END}",
            # Recorded in provenance because it is the single most misreadable
            # thing about this table: gain and loss do not span the same years.
            "gain_year_range": f"{fc_cfg.HANSEN_GAIN_YEAR_START}–"
                               f"{fc_cfg.HANSEN_GAIN_YEAR_END}",
            "gain_is_dated": False,
            "gain_not_updated_since": fc_cfg.HANSEN_GAIN_YEAR_END,
            "net_comparable_window": f"{fc_cfg.HANSEN_LOSS_YEAR_START}–"
                                     f"{fc_cfg.HANSEN_GAIN_YEAR_END}",
            "buffer_mode": mode,
            "radii_km": list(radii_km),
            "point": str(p),
        },
    )

    out = stack.reduceRegions(
        collection=fc, reducer=ee.Reducer.sum(),
        scale=EE_DEFAULT_SCALE_M, tileScale=EE_TILE_SCALE,
    ).getInfo()

    stats: dict[str, dict[str, float]] = {}
    for feat in out["features"]:
        props = feat["properties"]
        key = f"{float(props['radius_km']):g}"
        stats[key] = {
            "loss_ha": round(float(props.get("loss_ha") or 0.0), 2),
            "gain_ha": round(float(props.get("gain_ha") or 0.0), 2),
            "loss_gain_window_ha": round(float(props.get("loss_gain_window_ha") or 0.0), 2),
            "forest2000_ha": round(float(props.get("forest2000_ha") or 0.0), 2),
        }
    return stats, prov


def loss_by_year(
    p: Point,
    radius_km: float,
    mode: BufferMode = "disc",
    treecover_threshold: int | None = None,
) -> tuple[pd.DataFrame, Provenance]:
    """Annual tree-cover loss for one buffer — ``year, loss_ha``.

    One grouped reducer rather than 25 yearly calls: ``lossyear`` is already a
    per-pixel year code, so grouping the area sum by it gives the whole series
    in a single round-trip.
    """
    import ee

    get_ee()
    validate_for_analysis(p)

    threshold = (fc_cfg.HANSEN_TREECOVER_THRESHOLD
                 if treecover_threshold is None else treecover_threshold)
    gfc = hansen_image()
    forest2000 = gfc.select("treecover2000").gte(threshold)
    lossyear = gfc.select("lossyear").updateMask(
        gfc.select("loss").eq(1).And(forest2000))
    area_ha = ee.Image.pixelArea().divide(10_000.0).updateMask(lossyear.mask())

    prov = Provenance(
        name="world_loss_by_year",
        dataset_id=fc_cfg.HANSEN_GFC_DATASET,
        bands=["treecover2000", "loss", "lossyear"],
        scale_m=EE_DEFAULT_SCALE_M,
        reducer="sum grouped by lossyear",
        pixel_area_basis="ee.Image.pixelArea() per pixel",
        max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE,
        geometry=p.to_geojson(),
        extra={"treecover_threshold_pct": threshold, "radius_km": radius_km,
               "point": str(p)},
    )

    grouped = area_ha.addBands(lossyear).reduceRegion(
        reducer=ee.Reducer.sum().group(groupField=1, groupName="lossyear"),
        geometry=p.to_ee_point().buffer(radius_km * 1000.0),
        scale=EE_DEFAULT_SCALE_M,
        tileScale=EE_TILE_SCALE,
        maxPixels=EE_MAX_PIXELS,
    ).getInfo() or {}

    by_year = {
        int(g["lossyear"]) + fc_cfg.HANSEN_LOSS_YEAR_START - 1: float(g["sum"])
        for g in grouped.get("groups", []) if g.get("lossyear")
    }
    records = [
        {"year": y, "loss_ha": round(by_year.get(y, 0.0), 3)}
        for y in range(fc_cfg.HANSEN_LOSS_YEAR_START,
                       fc_cfg.HANSEN_LOSS_YEAR_END + 1)
    ]
    return pd.DataFrame.from_records(records), prov
