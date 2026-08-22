"""Above-ground biomass from ESA CCI Biomass_cci v6.0.

Ten snapshots, not a continuous series: 2007, 2010, then every year 2015–2022.
Each year is its own Earth Engine asset (``ESA/CCI/Above_Ground_Biomass/V6_0/
{year}``), unlike MapBiomas' single multi-band image — so the first thing this
module does is stitch them into one multi-band image (one band per year, per
measure), which is what turns "ten years × N buffers" back into the single
``reduceRegions`` round-trip the rest of this app relies on (see
mapbiomas_history.py's module docstring for why that matters).

Citation: Santoro, M.; Cartus, O. (2025). ESA Biomass Climate Change
Initiative (Biomass_cci): Global datasets of forest above-ground biomass for
the years 2007, 2010, 2015-2022, v6.0. NERC EDS CEDA.
doi:10.5285/95913ffb6467447ca72c4e9d8cf30501.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..config.settings import BUFFER_RADII_KM, EE_MAX_PIXELS, EE_TILE_SCALE
from .buffers import (
    BufferMode, BufferShape, buffer_collection,
    full_area_bbox, full_area_collection, full_area_geojson,
)
from .ee_client import get_ee
from .geo import Point, validate_for_analysis
from .provenance import Provenance

logger = logging.getLogger(__name__)

#: Not a continuous run — annual from 2015 on, but only two snapshots before
#: that (2007, 2010). The chart (components/charts.py) joins them with lines
#: for readability; the gaps are real, not missing data.
AGB_YEARS = [2007, 2010, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
AGB_ASSET_TEMPLATE = "ESA/CCI/Above_Ground_Biomass/V6_0/{year}"
AGB_DATASET_ID = "ESA/CCI/Above_Ground_Biomass/V6_0"
#: The product's own native resolution — reducing at MapBiomas' 30 m would
#: not add real detail, only cost (EE resamples a 100 m raster to fill it).
AGB_SCALE_M = 100

#: Map-layer visualization for one year's ``agb`` band (services/layers.py) —
#: the exact min/max/palette from the dataset's own Earth Engine catalog entry.
AGB_VIS = {"min": 0, "max": 500, "palette": ["white", "green"]}

BIOMASS_COLUMNS = [
    "radius_km", "year", "agb_mean_mgha", "agb_sd_mgha", "area_ha",
    "total_biomass_mg",
]


def _agb_band(year: int) -> str:
    return f"agb_{year}"


def _agb_sd_band(year: int) -> str:
    return f"agb_sd_{year}"


def _combined_image(years: list[int]) -> Any:
    """One image, two bands per year (mean + its uncertainty), all renamed so
    a single ``reduceRegions`` can read every year at once."""
    import ee

    bands = []
    for year in years:
        img = ee.Image(AGB_ASSET_TEMPLATE.format(year=year))
        bands.append(img.select("agb").rename(_agb_band(year)))
        bands.append(img.select("agb_sd").rename(_agb_sd_band(year)))
    return ee.Image.cat(bands)


def _mean_call(fc, image, bands: list[str], scale: int, tile_scale: int):
    import ee
    return (
        image.select(bands)
        .reduceRegions(collection=fc, reducer=ee.Reducer.mean(),
                       scale=scale, tileScale=tile_scale)
        .getInfo()
    )


def _area_sum_call(fc, scale: int, tile_scale: int):
    """True geodesic area of each feature's own geometry (m²) — not a nominal
    πr² formula, which would be right for one point's disc but badly wrong for
    the full-area bounding box (services.buffers.full_area_bbox), whose extent
    depends on wherever the selected points happen to be."""
    import ee
    return (
        ee.Image.pixelArea()
        .reduceRegions(collection=fc, reducer=ee.Reducer.sum(),
                       scale=scale, tileScale=tile_scale)
        .getInfo()
    )


def _biomass_from_collection(
    fc: Any,
    *,
    years: list[int],
    geometry: dict[str, Any] | None,
    point_label: str,
    mode: str,
    shape: str,
    radii_km: tuple[float, ...],
) -> tuple[pd.DataFrame, Provenance]:
    """Shared reduceRegions/retry/parsing body behind :func:`biomass_history`
    and :func:`full_area_biomass_history`.
    """
    import ee
    from concurrent.futures import ThreadPoolExecutor

    image = _combined_image(years)
    bands = [b for y in years for b in (_agb_band(y), _agb_sd_band(y))]

    prov = Provenance(
        name="biomass_history",
        dataset_id=AGB_DATASET_ID,
        bands=bands,
        scale_m=AGB_SCALE_M,
        reducer="mean (agb, agb_sd) + sum (pixelArea)",
        pixel_area_basis="measured ee.Image.pixelArea() sum per buffer/box",
        max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE,
        geometry=geometry,
        extra={"years": years, "buffer_mode": mode, "buffer_shape": shape,
               "radii_km": list(radii_km), "point": point_label,
               "citation": "Santoro & Cartus (2025), doi:10.5285/"
                           "95913ffb6467447ca72c4e9d8cf30501"},
    )

    scale, tile_scale = AGB_SCALE_M, EE_TILE_SCALE
    means = areas = None
    for attempt, (s, ts) in enumerate([(scale, tile_scale), (scale, 8), (200, 8)]):
        try:
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_mean = ex.submit(_mean_call, fc, image, bands, s, ts)
                f_area = ex.submit(_area_sum_call, fc, s, ts)
                means, areas = f_mean.result(), f_area.result()
            if attempt > 0:
                prov.degrade(
                    f"Retried at scale={s} m, tileScale={ts} after a failure at "
                    f"scale={scale} m, tileScale={tile_scale}.",
                    scale_m=s, tile_scale=ts,
                )
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("biomass attempt %s (scale=%s, tileScale=%s) failed: %s",
                           attempt + 1, s, ts, exc)
            if attempt == 2:
                raise

    area_ha_by_radius = {
        f["properties"]["radius_km"]: float(f["properties"].get("sum") or 0.0) / 10_000.0
        for f in areas["features"]
    }

    records: list[dict[str, Any]] = []
    for feat in means["features"]:
        props = feat["properties"]
        radius = float(props["radius_km"])
        area_ha = area_ha_by_radius.get(radius, 0.0)
        for year in years:
            mean_val = props.get(_agb_band(year))
            if mean_val is None:
                # Fully outside this year's coverage (masked everywhere in the
                # buffer) — dropped rather than recorded as zero, which would
                # misreport "no data" as "no biomass".
                continue
            sd_val = props.get(_agb_sd_band(year))
            records.append({
                "radius_km": radius,
                "year": year,
                "agb_mean_mgha": float(mean_val),
                "agb_sd_mgha": float(sd_val) if sd_val is not None else None,
                "area_ha": area_ha,
                "total_biomass_mg": float(mean_val) * area_ha,
            })

    df = pd.DataFrame.from_records(records, columns=BIOMASS_COLUMNS)
    if not df.empty:
        df = df.sort_values(["radius_km", "year"]).reset_index(drop=True)

    prov.extra["n_records"] = len(df)
    logger.info("Biomass for %s: %s records across %s buffers", point_label,
                len(df), len(area_ha_by_radius))
    return df, prov


def biomass_history(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
    shape: BufferShape = "circle",
    years: list[int] | None = None,
) -> tuple[pd.DataFrame, Provenance]:
    """Above-ground biomass (Mg/ha) and its uncertainty, by year and buffer.

    Ten Earth Engine assets (one per year) stitched into one image so the
    whole read is a single ``reduceRegions`` — see the module docstring.
    """
    get_ee()
    validate_for_analysis(p)

    years = years or AGB_YEARS
    fc = buffer_collection(p, radii_km, mode, shape)
    return _biomass_from_collection(
        fc, years=years, geometry=p.to_geojson(), point_label=str(p),
        mode=mode, shape=shape, radii_km=radii_km,
    )


def full_area_biomass_history(
    points: list[Point],
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    shape: BufferShape = "circle",
    years: list[int] | None = None,
) -> tuple[pd.DataFrame, Provenance]:
    """Biomass over the single bounding box enclosing every selected point's
    outer buffer — the "área total" reading, same trade as the other
    full_area_* siblings (no overlap, but the box covers land between
    clusters too).
    """
    get_ee()

    years = years or AGB_YEARS
    bbox = full_area_bbox(points, radii_km, shape)
    fc = full_area_collection(points, radii_km, shape, bbox=bbox)

    df, prov = _biomass_from_collection(
        fc, years=years, geometry=full_area_geojson(points, radii_km, shape, bbox=bbox),
        point_label=f"{len(points)} points (full area)", mode="full_area",
        shape=shape, radii_km=radii_km,
    )
    prov.extra["n_points"] = len(points)
    prov.extra["outer_radius_km"] = max(radii_km)
    prov.extra["bbox_wgs84"] = list(bbox)
    return df, prov


def aggregate_biomass(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Sum several conglomerados' biomass into one, per (radius, year).

    ``area_ha`` and ``total_biomass_mg`` **add** — mass and area are both
    extensive quantities, the same "sum over sampling units, overlap counted
    in each" reading ``aggregate_histories`` gives the land-cover sum.
    ``agb_mean_mgha`` is **recomputed** from the summed mass and area (a
    weighted average, larger buffers counting for more) rather than averaged
    across points directly — averaging Mg/ha values would let a small buffer's
    rate count exactly as much as a huge one's, the same trap
    ``aggregate_histories`` avoids for ``area_pct``. ``agb_sd_mgha`` is
    dropped: uncertainty does not combine by a plain average across
    independent buffers, and there is no pixel-level covariance available
    here to combine it rigorously.
    """
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(columns=["radius_km", "year", "area_ha",
                                     "total_biomass_mg", "agb_mean_mgha"])
    combined = pd.concat(frames, ignore_index=True)
    out = combined.groupby(["radius_km", "year"], as_index=False)[
        ["area_ha", "total_biomass_mg"]].sum()
    out["agb_mean_mgha"] = out["total_biomass_mg"] / out["area_ha"].clip(lower=1e-9)
    return out.sort_values(["radius_km", "year"]).reset_index(drop=True)
