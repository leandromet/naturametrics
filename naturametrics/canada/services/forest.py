"""Forest age (NTEMS) and forest change (Hansen GFC) over the buffers.

Canada's counterpart to :mod:`naturametrics.services.vegetation_age` and
:mod:`naturametrics.services.change_mask`, folded into one module because both
answer the same panel and both are national/global — unlike the ACI, neither has
a coverage hole to work around.

**Why this is simpler than the Brazil equivalent.** Brazil derives stand age by
running a counter over 40 years of the MapBiomas DSV series, which brings a
censoring ceiling and a whole vocabulary ("dated", "censored", "no change
observed") to explain it. NTEMS publishes the age directly, so this module
reduces a histogram and stops. There is no censored bin because there is no
censoring.

**The two gotchas, both verified on 2026-08-21:**

* NTEMS must be read through ``.mosaic()``. Sampling ``ee.Image(col.first())``
  returns null at every coordinate — see ``config/forest.py``.
* NTEMS is masked to forest. A null means "not forest", so the non-forest share
  of a buffer is the *complement* of the histogram total, not a data gap. It is
  reported explicitly for that reason.
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


def ntems_age_image():
    """The NTEMS forest-age raster, mosaicked.

    ``.mosaic()`` is not optional — see the module docstring.
    """
    import ee
    return ee.ImageCollection(fc_cfg.NTEMS_AGE_DATASET).mosaic()


def hansen_image():
    import ee
    return ee.Image(fc_cfg.HANSEN_GFC_DATASET)


# --------------------------------------------------------------------------- #
# Forest age
# --------------------------------------------------------------------------- #

def _binned_age_image():
    """Age remapped to bin indices, so one histogram gives the whole chart.

    Reducing raw ages would return up to ~400 distinct integer keys per buffer
    and leave the binning to pandas. Doing it Earth-Engine-side keeps the payload
    to seven keys and makes the bins a documented property of the query rather
    than of the client.
    """
    import ee

    age = ntems_age_image().select(fc_cfg.NTEMS_AGE_BAND)
    binned = ee.Image.constant(len(fc_cfg.AGE_BIN_EDGES) - 1)
    # Walk the edges downward so the first matching (lowest) bin wins.
    for idx, (lo, hi, _name) in reversed(list(enumerate(fc_cfg.AGE_BIN_EDGES))):
        binned = binned.where(age.lte(hi), idx)
    return binned.updateMask(age.mask()).rename("age_bin")


def buffer_forest_age(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
) -> tuple[pd.DataFrame, Provenance]:
    """Forested area by age bin and buffer.

    Long format — ``radius_km, bin, area_ha, color`` — plus the share of each
    buffer that is not forest at all.
    """
    import ee
    from concurrent.futures import ThreadPoolExecutor

    get_ee()
    validate_for_analysis(p)

    fc = buffer_collection(p, radii_km, mode)
    binned = _binned_age_image()

    prov = Provenance(
        name="canada_forest_age",
        dataset_id=fc_cfg.NTEMS_AGE_DATASET,
        bands=[fc_cfg.NTEMS_AGE_BAND],
        scale_m=EE_DEFAULT_SCALE_M,
        reducer="frequencyHistogram",
        pixel_area_basis="mean ee.Image.pixelArea() per buffer",
        max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE,
        geometry=p.to_geojson(),
        extra={
            "reference_year": fc_cfg.NTEMS_AGE_REFERENCE_YEAR,
            "buffer_mode": mode,
            "radii_km": list(radii_km),
            "point": str(p),
            "bins": fc_cfg.AGE_BIN_ORDER,
            "masked_to": "forested pixels only",
        },
    )

    def _hist(scale, tile_scale):
        return binned.reduceRegions(
            collection=fc, reducer=ee.Reducer.frequencyHistogram(),
            scale=scale, tileScale=tile_scale).getInfo()

    def _area(scale, tile_scale):
        return ee.Image.pixelArea().reduceRegions(
            collection=fc, reducer=ee.Reducer.mean(),
            scale=scale, tileScale=tile_scale).getInfo()

    hist = areas = None
    for attempt, (s, ts) in enumerate(
            [(EE_DEFAULT_SCALE_M, EE_TILE_SCALE), (EE_DEFAULT_SCALE_M, 8), (60, 8)]):
        try:
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_h, f_a = ex.submit(_hist, s, ts), ex.submit(_area, s, ts)
                hist, areas = f_h.result(), f_a.result()
            if attempt > 0:
                prov.degrade(f"Retried at scale={s} m, tileScale={ts}.",
                             scale_m=s, tile_scale=ts)
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("forest-age attempt %s failed: %s", attempt + 1, exc)
            if attempt == 2:
                raise

    px_area = {
        f["properties"]["radius_km"]: float(f["properties"].get("mean") or 900.0)
        for f in areas["features"]
    }

    records: list[dict[str, Any]] = []
    forest_ha: dict[float, float] = {}
    for feat in hist["features"]:
        props = feat["properties"]
        radius = float(props["radius_km"])
        area_per_px_ha = px_area.get(props["radius_km"], 900.0) / 10_000.0
        histogram = next(
            (v for k, v in props.items() if isinstance(v, dict)), {}
        )
        total = 0.0
        for bin_idx, count in histogram.items():
            count = float(count)
            if count <= 0:
                continue
            name = fc_cfg.AGE_BIN_ORDER[int(float(bin_idx))]
            area = count * area_per_px_ha
            total += area
            records.append({
                "radius_km": radius,
                "bin": name,
                "area_ha": area,
                "color": fc_cfg.age_bin_color(name),
            })
        forest_ha[radius] = total

    df = pd.DataFrame.from_records(
        records, columns=["radius_km", "bin", "area_ha", "color"])
    if not df.empty:
        df = (df.groupby(["radius_km", "bin", "color"], as_index=False)["area_ha"]
                .sum())
        order = {n: i for i, n in enumerate(fc_cfg.AGE_BIN_ORDER)}
        df["_o"] = df["bin"].map(order)
        df = df.sort_values(["radius_km", "_o"]).drop(columns="_o").reset_index(drop=True)

    # The complement: how much of each buffer NTEMS does not call forest. Derived
    # from the buffer's own geometric area rather than from a second query.
    #
    # Keys are ``:g``-formatted throughout ("5", not "5.0") because every reader
    # — age_summary here, the state layer, the export — looks radii up that way.
    # ``str(float)`` and ``f"{float:g}"` disagree, and the mismatch fails silently
    # as a zero rather than a KeyError.
    prov.extra["forest_ha"] = {f"{k:g}": round(v, 2) for k, v in forest_ha.items()}
    prov.extra["non_forest_ha"] = {
        f"{r:g}": round(max(disc_area_ha(r) - forest_ha.get(float(r), 0.0), 0.0), 2)
        for r in radii_km
    }
    prov.extra["mean_pixel_area_m2"] = {f"{float(k):g}": round(v, 2)
                                        for k, v in px_area.items()}
    return df, prov


def point_forest_age(p: Point) -> tuple[dict[str, Any], Provenance]:
    """Stand age at the clicked pixel itself, or ``None`` if it is not forest."""
    import ee

    get_ee()
    validate_for_analysis(p)

    prov = Provenance(
        name="canada_point_forest_age",
        dataset_id=fc_cfg.NTEMS_AGE_DATASET,
        bands=[fc_cfg.NTEMS_AGE_BAND],
        scale_m=EE_DEFAULT_SCALE_M,
        reducer="first",
        pixel_area_basis="n/a (single pixel)",
        max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE,
        geometry=p.to_geojson(),
        extra={"reference_year": fc_cfg.NTEMS_AGE_REFERENCE_YEAR,
               "point": str(p)},
    )

    raw = ntems_age_image().select(fc_cfg.NTEMS_AGE_BAND).reduceRegion(
        reducer=ee.Reducer.first(),
        geometry=p.to_ee_point(),
        scale=EE_DEFAULT_SCALE_M,
        tileScale=EE_TILE_SCALE,
        maxPixels=EE_MAX_PIXELS,
    ).getInfo() or {}

    value = raw.get(fc_cfg.NTEMS_AGE_BAND)
    age = int(value) if value is not None else None
    return {
        "age": age,
        "is_forest": age is not None,
        "reference_year": fc_cfg.NTEMS_AGE_REFERENCE_YEAR,
        "bin": fc_cfg.age_bin(age) if age is not None else None,
    }, prov


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
    stack = (
        area_ha.updateMask(gfc.select("loss").eq(1).And(forest2000)).rename("loss_ha")
        .addBands(area_ha.updateMask(gfc.select("gain").eq(1)).rename("gain_ha"))
        .addBands(area_ha.updateMask(forest2000).rename("forest2000_ha"))
    )

    prov = Provenance(
        name="canada_forest_change",
        dataset_id=fc_cfg.HANSEN_GFC_DATASET,
        bands=["treecover2000", "loss", "gain"],
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
            "gain_is_dated": False,
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
        name="canada_loss_by_year",
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


def aggregate_forest_age(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Sum several points' age histograms. Same contract as the ACI aggregator."""
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(columns=["radius_km", "bin", "area_ha", "color"])
    combined = pd.concat(frames, ignore_index=True)
    out = combined.groupby(["radius_km", "bin", "color"],
                           as_index=False)["area_ha"].sum()
    order = {n: i for i, n in enumerate(fc_cfg.AGE_BIN_ORDER)}
    out["_o"] = out["bin"].map(order)
    return out.sort_values(["radius_km", "_o"]).drop(columns="_o").reset_index(drop=True)


def age_summary(df: pd.DataFrame, radius_km: float,
                prov_extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Headline numbers beside the histogram.

    Median is the **area-weighted** median across bins, reported as a bin label
    rather than a number: NTEMS gives per-pixel ages but this frame is already
    binned, so quoting "63 years" would be precision the aggregate does not have.
    """
    if df is None or df.empty or "radius_km" not in df.columns:
        return {}
    sub = df[df["radius_km"] == radius_km]
    if sub.empty:
        return {}

    total = float(sub["area_ha"].sum())
    if total <= 0:
        return {}

    running, median_bin = 0.0, None
    for _, row in sub.iterrows():
        running += float(row["area_ha"])
        if running >= total / 2.0:
            median_bin = str(row["bin"])
            break

    non_forest = 0.0
    if prov_extra:
        non_forest = float(
            (prov_extra.get("non_forest_ha") or {}).get(f"{radius_km:g}", 0.0))

    return {
        "forest_area_ha": round(total, 1),
        "median_bin": median_bin,
        "non_forest_ha": round(non_forest, 1),
        "forest_pct": round(total / (total + non_forest) * 100.0, 1)
                      if (total + non_forest) > 0 else 0.0,
        "reference_year": fc_cfg.NTEMS_AGE_REFERENCE_YEAR,
    }
