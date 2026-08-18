"""MapBiomas land-cover history for a set of buffers.

This is the performance-critical path (doc/06-ee-layers.md §4). MapBiomas
Collection 10.1 ships all 40 years as 40 **bands of one image**, so the whole
"40 years × 4 buffers" matrix is a *single* ``reduceRegions`` — not because we
are rationing Earth Engine calls (the Partner tier makes that irrelevant) but
because one round-trip beats 160 sequential ones.

**Area accounting (decision D3).** Pixel counts alone would need a flat
0.09 ha/pixel assumption, which drifts with latitude. Instead a second, concurrent
call measures the *mean true pixel area* inside each buffer with
``ee.Image.pixelArea()``, and areas are ``count × mean_pixel_area``. Within a
single buffer the pixel area varies by far less than the classification error, so
this is exact for practical purposes and costs one extra cheap round-trip issued
in parallel. ``tests/test_area_accounting.py`` checks it against a per-class
grouped reducer, which is the textbook-exact method.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..config import mapbiomas as mb
from ..config.settings import (
    BUFFER_RADII_KM, EE_MAX_PIXELS, EE_TILE_SCALE, EE_DEFAULT_SCALE_M,
)
from .buffers import BufferMode, buffer_collection
from .geo import Point, validate_for_analysis
from .provenance import Provenance

logger = logging.getLogger(__name__)


def _histogram_call(fc, asset: str, bands: list[str], scale: int, tile_scale: int):
    import ee
    return (
        ee.Image(asset)
        .select(bands)
        .reduceRegions(
            collection=fc,
            reducer=ee.Reducer.frequencyHistogram(),
            scale=scale,
            tileScale=tile_scale,
        )
        .getInfo()
    )


def _pixel_area_call(fc, scale: int, tile_scale: int):
    """Mean true pixel area (m²) inside each buffer — the D3 area basis."""
    import ee
    return (
        ee.Image.pixelArea()
        .reduceRegions(
            collection=fc,
            reducer=ee.Reducer.mean(),
            scale=scale,
            tileScale=tile_scale,
        )
        .getInfo()
    )


def land_cover_history(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
    collection: str = mb.MAPBIOMAS_DEFAULT_COLLECTION,
    years: list[int] | None = None,
) -> tuple[pd.DataFrame, Provenance]:
    """Land-cover area by year, class and buffer.

    Returns a long-format frame — ``radius_km, year, class_id, pixels, area_ha`` —
    plus the provenance record that must travel with it (constraint C6).

    Long format rather than wide-by-year: 40 years × ~15 classes × 4 buffers is a
    natural long table, and wide-by-year breaks the moment the year range changes.
    """
    import ee
    from concurrent.futures import ThreadPoolExecutor

    validate_for_analysis(p)

    years = years or mb.MAPBIOMAS_YEARS
    bands = [mb.band_for_year(y) for y in years]
    asset = mb.MAPBIOMAS_COLLECTIONS[collection]
    fc = buffer_collection(p, radii_km, mode)

    prov = Provenance(
        name="landuse_history",
        dataset_id=asset,
        bands=bands,
        scale_m=EE_DEFAULT_SCALE_M,
        reducer="frequencyHistogram",
        pixel_area_basis="mean ee.Image.pixelArea() per buffer",
        max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE,
        geometry=p.to_geojson(),
        extra={"collection": collection, "buffer_mode": mode,
               "radii_km": list(radii_km), "point": str(p)},
    )

    scale, tile_scale = EE_DEFAULT_SCALE_M, EE_TILE_SCALE
    hist = areas = None

    # Retry ladder (doc/06 §4). Never coarsen without recording it.
    for attempt, (s, ts) in enumerate([(scale, tile_scale), (scale, 8), (60, 8)]):
        try:
            # Both calls are independent, so issue them together: the pair costs
            # one round-trip of wall-clock, not two.
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_hist = ex.submit(_histogram_call, fc, asset, bands, s, ts)
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
            logger.warning("history attempt %s (scale=%s, tileScale=%s) failed: %s",
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

        # Earth Engine names the reduceRegions output per BAND when several
        # bands are selected, but falls back to the reducer's own name
        # ("histogram") when there is exactly one. A parser that only looks for
        # "classification_*" therefore returns nothing at all for a single-year
        # query — silently, as an empty frame rather than an error.
        single_band = len(bands) == 1
        for key, histogram in props.items():
            if not isinstance(histogram, dict):
                continue
            if key.startswith("classification_"):
                year = int(key.rsplit("_", 1)[1])
            elif single_band and key == "histogram":
                year = years[0]
            else:
                continue
            for class_id, count in histogram.items():
                count = float(count)
                if count <= 0:
                    continue
                records.append({
                    "radius_km": float(radius),
                    "year": year,
                    "class_id": int(float(class_id)),
                    "pixels": count,
                    "area_ha": count * area_per_px_ha,
                })

    df = pd.DataFrame.from_records(
        records, columns=["radius_km", "year", "class_id", "pixels", "area_ha"]
    )
    if not df.empty:
        df["class_pt"] = df["class_id"].map(lambda c: mb.label(c, "pt"))
        df["class_en"] = df["class_id"].map(lambda c: mb.label(c, "en"))
        df["color"] = df["class_id"].map(mb.color)
        df = df.sort_values(["radius_km", "year", "area_ha"],
                            ascending=[True, True, False]).reset_index(drop=True)

    prov.extra["mean_pixel_area_m2"] = {str(k): round(v, 2) for k, v in px_area.items()}
    prov.extra["n_records"] = len(df)
    logger.info("History for %s: %s records across %s buffers", p, len(df), len(px_area))
    return df, prov


def to_shares(df: pd.DataFrame, radius_km: float) -> pd.DataFrame:
    """Per-year percentage shares for one buffer — what the stacked chart plots."""
    if df is None or df.empty or "radius_km" not in df.columns:
        return pd.DataFrame()
    sub = df[df["radius_km"] == radius_km].copy()
    if sub.empty:
        return sub
    totals = sub.groupby("year")["area_ha"].transform("sum")
    sub["area_pct"] = (sub["area_ha"] / totals * 100.0).fillna(0.0)
    return sub
