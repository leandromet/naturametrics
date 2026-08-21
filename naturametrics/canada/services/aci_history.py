"""AAFC Annual Crop Inventory history for a set of buffers.

Canada's counterpart to :mod:`naturametrics.services.mapbiomas_history`, and it
keeps that module's central performance property: **one** ``reduceRegions`` for
the whole "N years × 4 buffers" matrix rather than N×4 sequential calls.

Getting there takes one extra step here. MapBiomas ships all 40 years as 40
bands of a single image, so it can be reduced directly. The ACI is an
``ImageCollection`` of one single-band image per year, so this module stacks it
first — each year's ``landcover`` band renamed to ``aci_<year>``, then
``ee.Image.cat`` — which restores exactly the same shape. Measured 2026-08-21:
17 years × 4 buffers in **1.0 s**.

Area accounting follows decision D3 unchanged: a concurrent
``ee.Image.pixelArea()`` reduction gives the mean true pixel area per buffer, and
areas are ``count × mean_pixel_area``. A flat 0.09 ha/pixel would drift badly
here — more so than in Brazil, since Canada spans 41°N to 83°N and pixel area
falls off sharply with latitude.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ...config.settings import (
    BUFFER_RADII_KM, EE_DEFAULT_SCALE_M, EE_MAX_PIXELS, EE_TILE_SCALE,
)
from ...services.buffers import BufferMode, buffer_collection
from ...services.ee_client import get_ee
from ...services.provenance import Provenance
from ..config import aafc
from .geo import Point, validate_for_analysis

logger = logging.getLogger(__name__)


def stacked_aci_image(years: list[int] | None = None):
    """The ACI collection flattened into one multi-band image.

    One band per year, named by :func:`aafc.band_for_year`. This is the whole
    trick that lets the history be a single round-trip — see the module
    docstring.
    """
    import ee

    years = years or aafc.ACI_YEARS
    col = ee.ImageCollection(aafc.AACI_DATASET)
    bands = [
        ee.Image(col.filterDate(f"{y}-01-01", f"{y}-12-31").first())
        .rename(aafc.band_for_year(y))
        for y in years
    ]
    return ee.Image.cat(bands)


def aci_year_image(year: int):
    """One year's classification, for the map layer."""
    import ee

    col = ee.ImageCollection(aafc.AACI_DATASET)
    return ee.Image(col.filterDate(f"{year}-01-01", f"{year}-12-31").first())


def _histogram_call(fc, image, scale: int, tile_scale: int):
    import ee
    return image.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.frequencyHistogram(),
        scale=scale,
        tileScale=tile_scale,
    ).getInfo()


def _pixel_area_call(fc, scale: int, tile_scale: int):
    """Mean true pixel area (m²) inside each buffer — the D3 area basis."""
    import ee
    return ee.Image.pixelArea().reduceRegions(
        collection=fc,
        reducer=ee.Reducer.mean(),
        scale=scale,
        tileScale=tile_scale,
    ).getInfo()


def land_cover_history(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
    years: list[int] | None = None,
) -> tuple[pd.DataFrame, Provenance]:
    """Land-cover area by year, class and buffer.

    Returns a long-format frame — ``radius_km, year, class_id, pixels, area_ha``
    plus label/colour columns — and the provenance record that must travel with
    it (constraint C4/C6).

    Returns an **empty frame, not an error**, when the point is north of the ACI
    extent. That is the documented Canadian case (``services/geo.py``): the
    caller shows an explanatory empty state in this one panel while the forest
    panels answer normally.
    """
    from concurrent.futures import ThreadPoolExecutor

    # First statement, before validation, and idempotent — same reasoning as the
    # Brazil path: a tab open across a backend restart never re-runs on_mount.
    get_ee()
    validate_for_analysis(p)

    years = years or aafc.ACI_YEARS
    bands = [aafc.band_for_year(y) for y in years]
    fc = buffer_collection(p, radii_km, mode)
    image = stacked_aci_image(years)

    prov = Provenance(
        name="canada_landuse_history",
        dataset_id=aafc.AACI_DATASET,
        bands=bands,
        scale_m=EE_DEFAULT_SCALE_M,
        reducer="frequencyHistogram",
        pixel_area_basis="mean ee.Image.pixelArea() per buffer",
        max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE,
        geometry=p.to_geojson(),
        extra={
            "buffer_mode": mode,
            "radii_km": list(radii_km),
            "point": str(p),
            "year_range": f"{years[0]}–{years[-1]}",
            "national_coverage_from": aafc.ACI_NATIONAL_FROM,
        },
    )

    scale, tile_scale = EE_DEFAULT_SCALE_M, EE_TILE_SCALE
    hist = areas = None

    # Same retry ladder as Brazil. Never coarsen without recording it.
    for attempt, (s, ts) in enumerate([(scale, tile_scale), (scale, 8), (60, 8)]):
        try:
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_hist = ex.submit(_histogram_call, fc, image, s, ts)
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
            logger.warning("ACI history attempt %s (scale=%s, tileScale=%s) failed: %s",
                           attempt + 1, s, ts, exc)
            if attempt == 2:
                raise

    px_area = {
        f["properties"]["radius_km"]: float(f["properties"].get("mean") or 900.0)
        for f in areas["features"]
    }

    records: list[dict[str, Any]] = []
    single_band = len(bands) == 1
    for feat in hist["features"]:
        props = feat["properties"]
        radius = props["radius_km"]
        area_per_px_ha = px_area.get(radius, 900.0) / 10_000.0

        for key, histogram in props.items():
            if not isinstance(histogram, dict):
                continue
            # Same Earth Engine quirk the Brazil parser documents: reduceRegions
            # names its output per band when several are selected but falls back
            # to the reducer's own name for exactly one.
            if key.startswith("aci_"):
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
        df["class_en"] = df["class_id"].map(lambda c: aafc.label(int(c), "en"))
        df["class_pt"] = df["class_id"].map(lambda c: aafc.label(int(c), "pt"))
        df["color"] = df["class_id"].map(lambda c: aafc.color(int(c)))
        df = df.sort_values(["radius_km", "year", "area_ha"],
                            ascending=[True, True, False]).reset_index(drop=True)

    prov.extra["mean_pixel_area_m2"] = {str(k): round(v, 2) for k, v in px_area.items()}
    prov.extra["n_records"] = len(df)
    logger.info("ACI history for %s: %s records across %s buffers",
                p, len(df), len(px_area))
    return df, prov


def pixel_series(p: Point, years: list[int] | None = None
                 ) -> tuple[pd.DataFrame, Provenance]:
    """The ACI class of the clicked pixel itself, year by year.

    The point-scale companion to the buffer histories above — same role as the
    Brazil page's single-pixel series, and what the export's per-point tab uses.
    """
    import ee

    get_ee()
    validate_for_analysis(p)

    years = years or aafc.ACI_YEARS
    bands = [aafc.band_for_year(y) for y in years]
    image = stacked_aci_image(years)

    prov = Provenance(
        name="canada_pixel_series",
        dataset_id=aafc.AACI_DATASET,
        bands=bands,
        scale_m=EE_DEFAULT_SCALE_M,
        reducer="first",
        pixel_area_basis="n/a (single pixel)",
        max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE,
        geometry=p.to_geojson(),
        extra={"point": str(p), "year_range": f"{years[0]}–{years[-1]}"},
    )

    values = image.reduceRegion(
        reducer=ee.Reducer.first(),
        geometry=p.to_ee_point(),
        scale=EE_DEFAULT_SCALE_M,
        tileScale=EE_TILE_SCALE,
        maxPixels=EE_MAX_PIXELS,
    ).getInfo() or {}

    records = []
    for year in years:
        raw = values.get(aafc.band_for_year(year))
        class_id = int(raw) if raw is not None else None
        records.append({
            "year": year,
            "class_id": class_id,
            "class_en": aafc.label(class_id, "en") if class_id is not None else "No data",
            "class_pt": aafc.label(class_id, "pt") if class_id is not None else "Sem dado",
            "color": aafc.color(class_id) if class_id is not None else "#cccccc",
        })

    df = pd.DataFrame.from_records(records)
    prov.extra["n_missing"] = int(df["class_id"].isna().sum())
    return df, prov


def aggregate_histories(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Sum several points' buffer histories into one.

    Areas and pixel counts are **added** per (radius, year, class). Overlapping
    buffers are counted once in each point — the honest meaning of a sum over
    sampling units, and the reason the chart says so rather than implying the
    total is the area of the union. Same contract as the Brazil aggregator.
    """
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(columns=["radius_km", "year", "class_id", "pixels",
                                     "area_ha", "class_en", "class_pt", "color"])
    combined = pd.concat(frames, ignore_index=True)
    out = (
        combined.groupby(["radius_km", "year", "class_id"], as_index=False)
        [["pixels", "area_ha"]].sum()
    )
    out["class_en"] = out["class_id"].map(lambda c: aafc.label(int(c), "en"))
    out["class_pt"] = out["class_id"].map(lambda c: aafc.label(int(c), "pt"))
    out["color"] = out["class_id"].map(lambda c: aafc.color(int(c)))
    return out.sort_values(["radius_km", "year", "area_ha"],
                           ascending=[True, True, False]).reset_index(drop=True)


def preview_land_cover(p: Point, radius_km: float = 10.0) -> dict[str, Any]:
    """A quick two-year sketch of one buffer, for a hover card.

    Reads only the first nationally-covered year and the last, over a single
    buffer — deliberately not the full analysis, same rationale as the Brazil
    preview: the question while sweeping a cursor is what *changed*.
    """
    import ee

    get_ee()
    validate_for_analysis(p)

    first_year, last_year = aafc.ACI_NATIONAL_FROM, aafc.ACI_YEAR_END
    image = stacked_aci_image([first_year, last_year])
    raw = image.reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=p.to_ee_point().buffer(radius_km * 1000.0),
        scale=EE_DEFAULT_SCALE_M,
        tileScale=EE_TILE_SCALE,
        maxPixels=EE_MAX_PIXELS,
    ).getInfo() or {}

    def shares(band: str) -> dict[int, float]:
        hist = raw.get(band) or {}
        counts = {int(float(k)): float(v) for k, v in hist.items() if float(v) > 0}
        total = sum(counts.values())
        if not total:
            return {}
        return {k: v / total * 100.0 for k, v in counts.items()}

    first = shares(aafc.band_for_year(first_year))
    last = shares(aafc.band_for_year(last_year))
    if not last:
        return {"radius_km": radius_km, "rows": [], "empty": True}

    rows = [
        {
            "class_id": class_id,
            "class_en": aafc.label(class_id, "en"),
            "class_pt": aafc.label(class_id, "pt"),
            "color": aafc.color(class_id),
            "pct": round(pct, 1),
            "delta": round(pct - first.get(class_id, 0.0), 1),
        }
        for class_id, pct in sorted(last.items(), key=lambda kv: -kv[1])[:6]
    ]

    def natural(shares_map: dict[int, float]) -> float:
        return sum(v for k, v in shares_map.items()
                   if k in aafc.NATURAL_VEGETATION)

    return {
        "radius_km": radius_km,
        "first_year": first_year,
        "last_year": last_year,
        "rows": rows,
        "natural_first": round(natural(first), 1),
        "natural_last": round(natural(last), 1),
        "empty": False,
    }
