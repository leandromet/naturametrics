"""Disturbance history, time since disturbance, fire and canopy for the buffers (USA page).

Three families, all computed per buffer from public Earth Engine collections (see
``config/disturbance.py`` for what each is and what was verified):

* :func:`disturbance_history` — USFS **LCMS** ``Change`` by year and cause (wildfire, tree removal,
  insects/drought, wind…), area per buffer. One ``reduceRegions`` for years × buffers, like NLCD.
* :func:`time_since_disturbance` — the American stand of what the Canada page calls forest age.
  There is no measured stand-age raster for the US in Earth Engine, so this is **years since the last
  detected tree-removing disturbance** on pixels that are tree cover in the latest year, **censored
  at 1985**: a stand not disturbed since then is "41 or more", never "41 years old".
* :func:`fire_history` — **MTBS** burn severity by year and class (fires ≥ 1 000 acres in the west,
  ≥ 500 in the east; not every fire).
* :func:`canopy_history` — NLCD **Tree Canopy Cover** (USFS), mean canopy % per buffer and year.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import pandas as pd

from ...config.settings import (
    BUFFER_RADII_KM, EE_DEFAULT_SCALE_M, EE_MAX_PIXELS, EE_TILE_SCALE,
)
from ...services.buffers import BufferMode, buffer_collection
from ...services.ee_client import get_ee
from ...services.provenance import Provenance
from ..config import disturbance as cfg
from .geo import Point, region_of, validate_for_analysis
from .nlcd_history import _histogram_call, _pixel_area_call

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Images
# --------------------------------------------------------------------------- #
def _lcms(region: str):
    import ee
    return (ee.ImageCollection(cfg.LCMS)
            .filter(ee.Filter.eq("study_area", cfg.LCMS_STUDY_AREA[region])))


def lcms_change_stack(region: str, years: list[int] | None = None):
    """The ``Change`` band of every year as one multi-band image (``chg_<year>``)."""
    import ee
    years = years or cfg.LCMS_YEARS
    col = _lcms(region)
    return ee.Image.cat([
        ee.Image(col.filter(ee.Filter.eq("year", y)).first()).select("Change").rename(f"chg_{y}")
        for y in years])


def last_disturbance_year_image(region: str):
    """Year of the most recent tree-removing disturbance (masked where there is none)."""
    import ee

    def one(img):
        year = ee.Number(img.get("year"))
        hit = img.select("Change").remap(list(cfg.TREE_DISTURBANCE), [1] * len(cfg.TREE_DISTURBANCE), 0)
        return ee.Image.constant(year).updateMask(hit.eq(1)).rename("year").toInt16()
    return _lcms(region).map(one).max()


def time_since_image(region: str):
    """Bin index of years since the last disturbance, on tree pixels of the latest year.

    0..4 = the :data:`cfg.AGE_BINS`, 5 = censored (never disturbed since 1985). Masked elsewhere.
    """
    import ee
    latest = ee.Image(_lcms(region).filter(ee.Filter.eq("year", cfg.LCMS_YEAR_END)).first())
    trees = latest.select("Land_Cover").eq(1)
    last = last_disturbance_year_image(region)
    age = ee.Image.constant(cfg.LCMS_YEAR_END).subtract(last)
    binned = ee.Image(5)
    for i, (lo, hi, _label) in reversed(list(enumerate(cfg.AGE_BINS))):
        binned = binned.where(age.gte(lo).And(age.lte(hi)), i)
    return binned.updateMask(trees).rename("age_bin").toByte()


@lru_cache(maxsize=8)
def _mtbs_ids(region: str) -> tuple[str, ...]:
    import ee
    ids = ee.ImageCollection(cfg.MTBS).aggregate_array("system:index").getInfo()
    tag = f"mtbs_{cfg.MTBS_REGION[region]}_"
    return tuple(sorted(i for i in ids if i.startswith(tag)))


def mtbs_stack(region: str):
    """MTBS ``Severity`` of every available year, one band per year (``sev_<year>``)."""
    import ee
    bands = []
    for idx in _mtbs_ids(region):
        year = int(idx.rsplit("_", 1)[1])
        bands.append(ee.Image(ee.ImageCollection(cfg.MTBS).filter(
            ee.Filter.eq("system:index", idx)).first()).select("Severity").rename(f"sev_{year}"))
    return ee.Image.cat(bands) if bands else None


def mtbs_max_image(region: str):
    """Highest burn severity seen on each pixel across the record (1–5), for the map."""
    import ee
    col = ee.ImageCollection(cfg.MTBS).filter(ee.Filter.stringStartsWith(
        "system:index", f"mtbs_{cfg.MTBS_REGION[region]}_"))
    return col.map(lambda i: i.select("Severity").updateMask(i.select("Severity").gte(1)
                                                              .And(i.select("Severity").lte(5)))).max()


def tcc_stack(region: str, years: list[int] | None = None):
    import ee
    years = years or list(range(cfg.TCC_YEAR_START, cfg.TCC_YEAR_END + 1))
    col = (ee.ImageCollection(cfg.TCC)
           .filter(ee.Filter.eq("study_area", cfg.LCMS_STUDY_AREA[region])))
    return ee.Image.cat([
        ee.Image(col.filter(ee.Filter.eq("year", y)).first()).select(cfg.TCC_BAND).rename(f"tcc_{y}")
        for y in years])


def tcc_year_image(region: str, year: int):
    import ee
    col = (ee.ImageCollection(cfg.TCC)
           .filter(ee.Filter.eq("study_area", cfg.LCMS_STUDY_AREA[region])))
    return ee.Image(col.filter(ee.Filter.eq("year", year)).first()).select(cfg.TCC_BAND)


# --------------------------------------------------------------------------- #
# Plumbing shared by the four analyses
# --------------------------------------------------------------------------- #
def _prov(name: str, dataset: str, bands: list[str], reducer: str, p: Point,
          radii: tuple[float, ...], mode: str, extra: dict[str, Any]) -> Provenance:
    return Provenance(
        name=name, dataset_id=dataset, bands=bands, scale_m=EE_DEFAULT_SCALE_M, reducer=reducer,
        pixel_area_basis="mean ee.Image.pixelArea() per buffer", max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE, geometry=p.to_geojson(),
        extra={"buffer_mode": mode, "radii_km": list(radii), "point": str(p), **extra})


def _run(prov: Provenance, call, label: str):
    """The retry ladder every history uses; never coarsens without recording it."""
    scale, tile_scale = EE_DEFAULT_SCALE_M, EE_TILE_SCALE
    for attempt, (s, ts) in enumerate([(scale, tile_scale), (scale, 8), (60, 8)]):
        try:
            out = call(s, ts)
            if attempt > 0:
                prov.degrade(f"Retried at scale={s} m, tileScale={ts} after a failure at "
                             f"scale={scale} m, tileScale={tile_scale}.", scale_m=s, tile_scale=ts)
            return out
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s attempt %s (scale=%s, tileScale=%s) failed: %s", label, attempt + 1, s, ts, exc)
            if attempt == 2:
                raise


def _histograms(fc, image, with_area: bool):
    from concurrent.futures import ThreadPoolExecutor

    def call(s, ts):
        with ThreadPoolExecutor(max_workers=2) as ex:
            fh = ex.submit(_histogram_call, fc, image, s, ts)
            fa = ex.submit(_pixel_area_call, fc, s, ts, image)
            return fh.result(), fa.result()
    return call


def _px_area(areas) -> dict:
    return {f["properties"]["radius_km"]: float(f["properties"].get("mean") or 900.0)
            for f in areas["features"]}


# --------------------------------------------------------------------------- #
# Public analyses
# --------------------------------------------------------------------------- #
def disturbance_history(p: Point, radii_km: tuple[float, ...] = BUFFER_RADII_KM,
                        mode: BufferMode = "disc") -> tuple[pd.DataFrame, Provenance]:
    """LCMS change by year and class, area per buffer: ``radius_km, year, class_id, area_ha``.

    Stable and not-processed pixels are dropped; the gain class (14) is kept so the chart can show
    regrowth against loss.
    """
    get_ee()
    validate_for_analysis(p)
    region = region_of(p) or "conus"
    fc = buffer_collection(p, radii_km, mode)
    image = lcms_change_stack(region)
    prov = _prov("usa_disturbance_history", cfg.LCMS, [f"chg_{y}" for y in cfg.LCMS_YEARS],
                 "frequencyHistogram", p, radii_km, mode, {"region": region})
    hist, areas = _run(prov, _histograms(fc, image, True), "LCMS history")
    px = _px_area(areas)
    rows: list[dict[str, Any]] = []
    for feat in hist["features"]:
        props = feat["properties"]; radius = props["radius_km"]; ha_px = px.get(radius, 900.0) / 10_000.0
        for key, h in props.items():
            if not isinstance(h, dict) or not key.startswith("chg_"):
                continue
            year = int(key.split("_")[1])
            for cid, count in h.items():
                c = int(float(cid))
                if 1 <= c <= 14 and float(count) > 0:
                    rows.append({"radius_km": float(radius), "year": year, "class_id": c,
                                 "area_ha": float(count) * ha_px})
    df = pd.DataFrame.from_records(rows, columns=["radius_km", "year", "class_id", "area_ha"])
    if not df.empty:
        df["class_en"] = df["class_id"].map(lambda c: cfg.change_label(int(c), "en"))
        df["class_pt"] = df["class_id"].map(lambda c: cfg.change_label(int(c), "pt"))
        df["color"] = df["class_id"].map(lambda c: cfg.CHANGE_COLORS[int(c)])
        df = df.sort_values(["radius_km", "year", "class_id"]).reset_index(drop=True)
    prov.extra["n_records"] = len(df)
    return df, prov


def time_since_disturbance(p: Point, radii_km: tuple[float, ...] = BUFFER_RADII_KM,
                           mode: BufferMode = "disc") -> tuple[pd.DataFrame, Provenance]:
    """Tree area per buffer by years since the last disturbance: ``radius_km, bin, area_ha, color``.

    ``prov.extra["non_tree_ha"]`` carries, per radius, the buffer area that is not tree cover in the
    latest LCMS year (the complement: reported, not dropped).
    """
    import ee
    get_ee()
    validate_for_analysis(p)
    region = region_of(p) or "conus"
    fc = buffer_collection(p, radii_km, mode)
    image = time_since_image(region)
    prov = _prov("usa_time_since_disturbance", cfg.LCMS, ["age_bin"], "frequencyHistogram", p, radii_km,
                 mode, {"region": region, "censored_at": cfg.LCMS_YEAR_START,
                        "tree_disturbance_classes": list(cfg.TREE_DISTURBANCE),
                        "reference_year": cfg.LCMS_YEAR_END})
    hist, areas = _run(prov, _histograms(fc, image, True), "LCMS age")
    px = _px_area(areas)
    rows, non_tree = [], {}
    for feat in hist["features"]:
        props = feat["properties"]; radius = props["radius_km"]; ha_px = px.get(radius, 900.0) / 10_000.0
        h = props.get("histogram") or props.get("age_bin") or {}
        total = 0.0
        for b, count in h.items():
            label = cfg.AGE_ORDER[int(float(b))]
            area = float(count) * ha_px
            total += area
            rows.append({"radius_km": float(radius), "bin": label, "area_ha": area,
                         "color": cfg.AGE_COLORS[label]})
        non_tree[f"{radius:g}"] = None            # filled by the caller from the nominal disc area
    df = pd.DataFrame.from_records(rows, columns=["radius_km", "bin", "area_ha", "color"])
    prov.extra["non_tree_ha"] = non_tree
    return df, prov


def fire_history(p: Point, radii_km: tuple[float, ...] = BUFFER_RADII_KM,
                 mode: BufferMode = "disc") -> tuple[pd.DataFrame, Provenance]:
    """MTBS burned area by year and severity class: ``radius_km, year, class_id, area_ha``."""
    get_ee()
    validate_for_analysis(p)
    region = region_of(p) or "conus"
    image = mtbs_stack(region)
    prov = _prov("usa_fire_history", cfg.MTBS, [], "frequencyHistogram", p, radii_km, mode,
                 {"region": region, "note": "MTBS maps fires of at least 1,000 acres (west) / 500 (east)"})
    if image is None:
        return pd.DataFrame(columns=["radius_km", "year", "class_id", "area_ha"]), prov
    fc = buffer_collection(p, radii_km, mode)
    hist, areas = _run(prov, _histograms(fc, image, True), "MTBS history")
    px = _px_area(areas)
    rows: list[dict[str, Any]] = []
    for feat in hist["features"]:
        props = feat["properties"]; radius = props["radius_km"]; ha_px = px.get(radius, 900.0) / 10_000.0
        for key, h in props.items():
            if not isinstance(h, dict) or not key.startswith("sev_"):
                continue
            year = int(key.split("_")[1])
            for cid, count in h.items():
                c = int(float(cid))
                if 1 <= c <= 5 and float(count) > 0:
                    rows.append({"radius_km": float(radius), "year": year, "class_id": c,
                                 "area_ha": float(count) * ha_px})
    df = pd.DataFrame.from_records(rows, columns=["radius_km", "year", "class_id", "area_ha"])
    if not df.empty:
        df["class_en"] = df["class_id"].map(lambda c: cfg.severity_label(int(c), "en"))
        df["class_pt"] = df["class_id"].map(lambda c: cfg.severity_label(int(c), "pt"))
        df["color"] = df["class_id"].map(lambda c: cfg.SEVERITY_COLORS[int(c)])
        df = df.sort_values(["radius_km", "year", "class_id"]).reset_index(drop=True)
    prov.extra["years_available"] = [int(i.rsplit("_", 1)[1]) for i in _mtbs_ids(region)]
    return df, prov


def canopy_history(p: Point, radii_km: tuple[float, ...] = BUFFER_RADII_KM,
                   mode: BufferMode = "disc") -> tuple[pd.DataFrame, Provenance]:
    """Mean tree-canopy cover (%) per buffer and year: ``radius_km, year, canopy_pct``."""
    import ee
    get_ee()
    validate_for_analysis(p)
    region = region_of(p) or "conus"
    fc = buffer_collection(p, radii_km, mode)
    years = list(range(cfg.TCC_YEAR_START, cfg.TCC_YEAR_END + 1))
    image = tcc_stack(region, years)
    prov = _prov("usa_canopy_history", cfg.TCC, [f"tcc_{y}" for y in years], "mean", p, radii_km, mode,
                 {"region": region})

    def call(s, ts):
        return image.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=s,
                                   tileScale=ts).getInfo()
    stats = _run(prov, call, "TCC history")
    rows = []
    for feat in stats["features"]:
        props = feat["properties"]
        for y in years:
            v = props.get(f"tcc_{y}")
            if v is not None:
                rows.append({"radius_km": float(props["radius_km"]), "year": y, "canopy_pct": round(float(v), 2)})
    return pd.DataFrame.from_records(rows, columns=["radius_km", "year", "canopy_pct"]), prov
