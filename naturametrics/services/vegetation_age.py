"""Forest/vegetation age from the MapBiomas Deforestation & Secondary Vegetation product.

See doc/10-forest-age.md (estimator "E1") and config/vegetation_age.py for why this reads
a published MapBiomas asset rather than re-deriving its classification from raw
coverage bands. This module does the part that has no upstream equivalent: turning
DSV's year-by-year class codes into a running "years since last disturbance" age,
which is the piece the reference script (doc/mapbiomas_veg_secundaria.js) does not
itself compute either — it only produces the classification this module consumes.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from ..config import vegetation_age as fa
from ..config.settings import (
    BUFFER_RADII_KM, EE_MAX_PIXELS, EE_TILE_SCALE, EE_DEFAULT_SCALE_M,
)
from .buffers import (
    BufferMode, BufferShape, buffer_collection,
    full_area_bbox, full_area_collection, full_area_geojson,
)
from .ee_client import get_ee
from .geo import Point, validate_for_analysis
from .mapbiomas_history import _pixel_area_call  # shared D3 area-per-buffer basis
from .provenance import Provenance

logger = logging.getLogger(__name__)


def _forest_age_bands(dsv) -> Any:
    """One age band per DSV year, built as a running counter.

    The default each year is "one year older than last year" — class 2 or 3, stable
    vegetation continuing. Three exceptions overwrite that default, and the order
    among them does not matter because the DSV codes 0–7 partition into disjoint
    sets: a suppression event (4 or 6) zeroes the clock; a regrowth event (5) starts
    it at 1; anthropic/no-data/noise (1, 0, 7) — not vegetation at all this year —
    also reads as 0 rather than carrying a stale count forward, since DSV records
    nothing to carry through a year it calls anthropic.

    A pixel that is class 2 for the *entire* record reaches exactly
    :data:`config.vegetation_age.CENSORED_AGE` (one increment per year, from a start of
    0) — and, by construction, that is the *only* way to reach that value: any
    regrowth event resets the clock to 1, and DSV records at most one regrowth per
    pixel in this window. So "hit the ceiling" and "primary vegetation, right-
    censored at the start of the record" are the same condition here, and no
    separate censored flag needs to be threaded through the pixel computation —
    callers derive it with a plain ``>= CENSORED_AGE`` check.
    """
    import ee

    counter = ee.Image(0)
    bands = []
    for year in fa.DSV_YEARS:
        cls = dsv.select(fa.dsv_band_for_year(year))
        suppressed = cls.eq(4).Or(cls.eq(6))
        regrowth = cls.eq(5)
        other = cls.eq(1).Or(cls.eq(0)).Or(cls.eq(7))
        counter = (
            counter.add(1)
            .where(suppressed, 0)
            .where(regrowth, 1)
            .where(other, 0)
        )
        bands.append(counter.rename(f"age_{year}"))
    return ee.Image.cat(bands)


def point_forest_age_series(p: Point) -> tuple[pd.DataFrame, Provenance]:
    """Age and DSV class at the point's own pixel, one row per DSV year.

    Mirrors ``point_pixel_series`` in mapbiomas_history.py in shape and honesty: one
    30 m pixel, no averaging, same "one bad year looks like a spurious dip" caveat.
    This is the line-graph source — a single trace that climbs while the pixel is
    forested, drops to 0 on a detected clearing, and either climbs again (regrowth)
    or plateaus at the censored ceiling (never disturbed in the record).
    """
    import ee

    get_ee()
    validate_for_analysis(p)

    dsv = ee.Image(fa.DSV_ASSET)
    age_img = _forest_age_bands(dsv)
    class_bands = [fa.dsv_band_for_year(y) for y in fa.DSV_YEARS]
    combined = age_img.addBands(dsv.select(class_bands))

    prov = Provenance(
        name="point_forest_age",
        dataset_id=fa.DSV_ASSET,
        bands=class_bands,
        scale_m=EE_DEFAULT_SCALE_M,
        reducer="first",
        pixel_area_basis="n/a — single pixel, no area computed",
        max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE,
        geometry=p.to_geojson(),
        extra={"point": str(p), "estimator": "E1 (MapBiomas DSV v3)"},
    )

    values = (
        combined.reduceRegion(
            reducer=ee.Reducer.first(),
            geometry=p.to_ee_point(),
            scale=EE_DEFAULT_SCALE_M,
            tileScale=EE_TILE_SCALE,
            maxPixels=EE_MAX_PIXELS,
        ).getInfo()
    ) or {}

    records = []
    for year in fa.DSV_YEARS:
        raw_age = values.get(f"age_{year}")
        raw_class = values.get(fa.dsv_band_for_year(year))
        age = int(raw_age) if raw_age is not None else None
        class_id = int(raw_class) if raw_class is not None else None
        records.append({
            "year": year,
            "age": age,
            "censored": age is not None and age >= fa.CENSORED_AGE,
            "class_id": class_id,
            "class_pt": fa.dsv_label(class_id, "pt"),
            "class_en": fa.dsv_label(class_id, "en"),
            "color": fa.dsv_color(class_id),
        })

    df = pd.DataFrame.from_records(records)
    prov.extra["n_years"] = len(df)
    prov.extra["n_missing"] = int(df["age"].isna().sum())
    return df, prov


def buffer_forest_age_histogram(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
    shape: BufferShape = "circle",
) -> tuple[pd.DataFrame, Provenance]:
    """Age-class distribution of *currently* vegetated pixels, per buffer.

    A snapshot of the last DSV year (doc/10 §6: the distribution is reported per
    buffer, not as a time series — the point series above already carries the "how
    did we get here" story). Age-0 pixels — this year not class 2/3: anthropic,
    water, no-data, mid-transition — are dropped before histogramming rather than
    reported as "0 years old"; that would misreport "not currently forest" as
    "freshly established forest", a different and wrong claim.
    """
    import ee

    get_ee()
    validate_for_analysis(p)

    dsv = ee.Image(fa.DSV_ASSET)
    age_img = _forest_age_bands(dsv)
    last = age_img.select(f"age_{fa.DSV_YEAR_END}")
    age_final = last.updateMask(last.gt(0)).rename("age")

    fc = buffer_collection(p, radii_km, mode, shape)
    return _forest_age_from_collection(
        fc, age_final, geometry=p.to_geojson(), point_label=str(p),
        mode=mode, shape=shape, radii_km=radii_km,
    )


def full_area_forest_age_histogram(
    points: list[Point],
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    shape: BufferShape = "circle",
) -> tuple[pd.DataFrame, Provenance]:
    """Forest-age histogram over the single bounding box enclosing every
    selected point's outer buffer — the age-model counterpart of
    ``mapbiomas_history.full_area_land_cover_history``, same trade: no overlap
    to double-count, at the cost of also covering land between clusters.
    """
    import ee

    get_ee()

    dsv = ee.Image(fa.DSV_ASSET)
    age_img = _forest_age_bands(dsv)
    last = age_img.select(f"age_{fa.DSV_YEAR_END}")
    age_final = last.updateMask(last.gt(0)).rename("age")

    bbox = full_area_bbox(points, radii_km, shape)
    fc = full_area_collection(points, radii_km, shape, bbox=bbox)

    df, prov = _forest_age_from_collection(
        fc, age_final,
        geometry=full_area_geojson(points, radii_km, shape, bbox=bbox),
        point_label=f"{len(points)} points (full area)",
        mode="full_area", shape=shape, radii_km=radii_km,
    )
    prov.extra["n_points"] = len(points)
    prov.extra["outer_radius_km"] = max(radii_km)
    prov.extra["bbox_wgs84"] = list(bbox)
    return df, prov


def region_forest_age_histogram(geom: Any, label: str) -> tuple[pd.DataFrame, Provenance]:
    """Forest-age histogram over a user-drawn/uploaded region — the polygon
    counterpart of :func:`full_area_forest_age_histogram`."""
    import ee

    from .region_geometry import region_collection, region_geojson

    get_ee()

    dsv = ee.Image(fa.DSV_ASSET)
    age_img = _forest_age_bands(dsv)
    last = age_img.select(f"age_{fa.DSV_YEAR_END}")
    age_final = last.updateMask(last.gt(0)).rename("age")

    fc = region_collection(geom, label)
    df, prov = _forest_age_from_collection(
        fc, age_final, geometry=region_geojson(geom, label), point_label=label,
        mode="region", shape="polygon", radii_km=(0.0,),
    )
    prov.extra["region_label"] = label
    return df, prov


def _forest_age_from_collection(
    fc: Any,
    age_final: Any,
    *,
    geometry: dict[str, Any] | None,
    point_label: str,
    mode: str,
    shape: str,
    radii_km: tuple[float, ...],
) -> tuple[pd.DataFrame, Provenance]:
    """Shared reduceRegions/retry/parsing body behind
    :func:`buffer_forest_age_histogram` and :func:`full_area_forest_age_histogram`.
    """
    import ee
    from concurrent.futures import ThreadPoolExecutor

    last_band = f"age_{fa.DSV_YEAR_END}"

    prov = Provenance(
        name="buffer_forest_age",
        dataset_id=fa.DSV_ASSET,
        bands=[last_band],
        scale_m=EE_DEFAULT_SCALE_M,
        reducer="frequencyHistogram",
        pixel_area_basis="mean ee.Image.pixelArea() per buffer (same basis as land-use history)",
        max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE,
        geometry=geometry,
        extra={"buffer_mode": mode, "buffer_shape": shape, "radii_km": list(radii_km),
               "point": point_label, "estimator": "E1 (MapBiomas DSV v3)",
               "reference_year": fa.DSV_YEAR_END},
    )

    def _hist_call(fc, scale, tile_scale):
        return (
            age_final.reduceRegions(
                collection=fc, reducer=ee.Reducer.frequencyHistogram(),
                scale=scale, tileScale=tile_scale,
            ).getInfo()
        )

    scale, tile_scale = EE_DEFAULT_SCALE_M, EE_TILE_SCALE
    hist = areas = None
    for attempt, (s, ts) in enumerate([(scale, tile_scale), (scale, 8), (60, 8)]):
        try:
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_hist = ex.submit(_hist_call, fc, s, ts)
                f_area = ex.submit(_pixel_area_call, fc, s, ts)
                hist, areas = f_hist.result(), f_area.result()
            if attempt > 0:
                prov.degrade(
                    f"Retried at scale={s} m, tileScale={ts} after a failure at "
                    f"scale={scale} m, tileScale={tile_scale}.",
                    scale_m=s, tile_scale=ts,
                )
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("forest-age attempt %s (scale=%s, tileScale=%s) failed: %s",
                           attempt + 1, s, ts, exc)
            if attempt == 2:
                raise

    px_area = {
        f["properties"]["radius_km"]: float(f["properties"].get("mean") or 900.0)
        for f in areas["features"]
    }

    records: list[dict[str, Any]] = []
    for feat in hist["features"]:
        props = feat["properties"]
        radius = props["radius_km"]
        area_per_px_ha = px_area.get(radius, 900.0) / 10_000.0
        # reduceRegions names its output per BAND when several bands are selected,
        # but falls back to the reducer's own name ("histogram") for exactly one —
        # the same gotcha documented in mapbiomas_history.land_cover_history.
        histogram = props.get("age") or props.get("histogram") or {}
        for age_str, count in histogram.items():
            count = float(count)
            if count <= 0:
                continue
            age = int(float(age_str))
            records.append({
                "radius_km": float(radius),
                "age": age,
                "bin": fa.age_bin(age),
                "censored": age >= fa.CENSORED_AGE,
                "pixels": count,
                "area_ha": count * area_per_px_ha,
            })

    df = pd.DataFrame.from_records(
        records, columns=["radius_km", "age", "bin", "censored", "pixels", "area_ha"]
    )
    if not df.empty:
        df["color"] = df.apply(
            lambda r: fa.CENSORED_COLOR if r["censored"]
            else fa.AGE_BIN_COLORS.get(r["bin"], "#6cb84d"),
            axis=1,
        )
        df = df.sort_values(["radius_km", "age"]).reset_index(drop=True)

    prov.extra["mean_pixel_area_m2"] = {str(k): round(v, 2) for k, v in px_area.items()}
    prov.extra["n_records"] = len(df)
    logger.info("Forest age for %s: %s records across %s buffers", point_label, len(df), len(px_area))
    return df, prov


def aggregate_forest_age(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Sum several conglomerados' buffer age histograms.

    Same reading as ``aggregate_histories`` in mapbiomas_history.py: areas add,
    percentages are recomputed from the sums, and overlapping buffers are counted
    once per sampling unit rather than once for the union (doc/10 and doc/06 agree
    on this — a sum over sampling units is not an area of a union).
    """
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(
            columns=["radius_km", "age", "bin", "censored", "pixels", "area_ha", "color"]
        )
    combined = pd.concat(frames, ignore_index=True)
    out = (
        combined.groupby(["radius_km", "age", "bin", "censored"], as_index=False)
        [["pixels", "area_ha"]].sum()
    )
    out["color"] = out.apply(
        lambda r: fa.CENSORED_COLOR if r["censored"]
        else fa.AGE_BIN_COLORS.get(r["bin"], "#6cb84d"),
        axis=1,
    )
    return out.sort_values(["radius_km", "age"]).reset_index(drop=True)


def age_summary(df: pd.DataFrame, radius_km: float, lang: str = "pt") -> dict[str, Any]:
    """Headline numbers for one buffer — doc/10 §5.1: never a bare mean.

    Median age is computed only over the *dated* (non-censored) area, and the
    censored share is surfaced next to it rather than folded in — the two
    requirements §5.1 calls out by name.
    """
    if df is None or df.empty or "radius_km" not in df.columns:
        return {}
    sub = df[df["radius_km"] == radius_km]
    if sub.empty:
        return {}

    total_ha = float(sub["area_ha"].sum())
    censored = sub[sub["censored"]]
    dated = sub[~sub["censored"]]
    censored_ha = float(censored["area_ha"].sum())
    dated_ha = float(dated["area_ha"].sum())

    median_age = None
    if dated_ha > 0 and not dated.empty:
        values = dated["age"].to_numpy(dtype=float)
        weights = dated["area_ha"].to_numpy(dtype=float)
        order = np.argsort(values)
        values, weights = values[order], weights[order]
        cum = np.cumsum(weights)
        idx = int(np.searchsorted(cum, weights.sum() / 2.0))
        median_age = float(values[min(idx, len(values) - 1)])

    return {
        "total_natural_area_ha": round(total_ha, 1),
        "censored_area_ha": round(censored_ha, 1),
        "censored_pct": round(censored_ha / total_ha * 100.0, 1) if total_ha else 0.0,
        "dated_area_ha": round(dated_ha, 1),
        "median_dated_age": round(median_age, 1) if median_age is not None else None,
        "censored_label": fa.censored_label(lang),
    }
