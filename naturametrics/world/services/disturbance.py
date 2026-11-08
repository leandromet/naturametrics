"""Disturbance history, time since disturbance, fire and canopy for the buffers (world page).

Four analyses, all computed per buffer from global public Earth Engine collections (see
``config/disturbance.py`` for what each is):

* :func:`disturbance_history` — Hansen tree-cover **loss** by year, area per buffer (the cause is not
  recorded by the product).
* :func:`time_since_disturbance` — **years since the last detected loss** on pixels that were forest
  in 2000, **censored at 2001**: a stand never lost since then is "25 or more", never "25 years old".
* :func:`fire_history` — **MODIS MCD64A1** burned area by year (500 m: small fires fall between pixels).
* :func:`canopy_history` — mean tree canopy (%) per buffer and year: Hansen's 2000 canopy minus the
  pixels lost by that year; regrowth after a loss is not counted.
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
from ..config import disturbance as cfg
from ..config import forest as fc_cfg
from .geo import Point, region_of, validate_for_analysis
from .glc_history import _histogram_call, _pixel_area_call

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Images
# --------------------------------------------------------------------------- #
def _hansen():
    import ee
    return ee.Image(cfg.HANSEN)


def _forest2000(threshold: int | None = None):
    thr = fc_cfg.HANSEN_TREECOVER_THRESHOLD if threshold is None else threshold
    return _hansen().select("treecover2000").gte(thr)


def last_disturbance_year_image():
    """Year of the most recent tree-cover loss, on pixels that were forest in 2000 (masked elsewhere)."""
    g = _hansen()
    lost = g.select("loss").eq(1).And(_forest2000())
    return g.select("lossyear").add(cfg.LOSS_YEAR_START - 1).updateMask(lost).rename("last_loss_year")


def time_since_image():
    """Age class of every forest-in-2000 pixel: 0..4 = the :data:`cfg.AGE_BINS`, 5 = censored (never
    lost since 2001). Masked where there was no forest in 2000."""
    import ee

    g = _hansen()
    forest = _forest2000()
    lost = g.select("loss").eq(1)
    year = g.select("lossyear").add(cfg.LOSS_YEAR_START - 1)
    age = ee.Image.constant(cfg.LOSS_YEAR_END).subtract(year)
    binned = ee.Image(len(cfg.AGE_BINS))                      # 5 = censored, until a bin claims the pixel
    for i, (lo, hi, _label) in reversed(list(enumerate(cfg.AGE_BINS))):
        binned = binned.where(lost.And(age.gte(lo)).And(age.lte(hi)), i)
    return binned.updateMask(forest).rename("age_bin").toByte()


def burn_last_year_image():
    """Year of the most recent burn seen by MODIS (2001–), masked where nothing burned."""
    import ee

    col = ee.ImageCollection(cfg.MODIS_BURN).select("BurnDate")
    years = [col.filterDate(f"{y}-01-01", f"{y + 1}-01-01").max().gt(0).multiply(y).selfMask()
             for y in cfg.BURN_YEARS]
    return ee.ImageCollection.fromImages(years).max().rename("last_burn_year")


def burn_stack(years: list[int] | None = None):
    """Burned yes/no for every year as one multi-band image (``burn_<year>``)."""
    import ee

    years = years or cfg.BURN_YEARS
    col = ee.ImageCollection(cfg.MODIS_BURN).select("BurnDate")
    return ee.Image.cat([
        col.filterDate(f"{y}-01-01", f"{y + 1}-01-01").max().unmask(0).gt(0).rename(f"burn_{y}")
        for y in years])


def canopy_stack(years: list[int] | None = None):
    """Canopy % of every year as one multi-band image (``canopy_<year>``): the 2000 canopy, zero on
    the pixels lost in or before that year."""
    import ee

    years = years or cfg.CANOPY_YEARS
    g = _hansen()
    tc = g.select("treecover2000")
    lossyear = g.select("lossyear")                           # 0 = no loss, else 1..25
    bands = []
    for y in years:
        code = y - cfg.LOSS_YEAR_START + 1                    # last lossyear code that counts by year y
        lost = lossyear.gt(0).And(lossyear.lte(code))
        bands.append(tc.where(lost, 0).rename(f"canopy_{y}"))
    return ee.Image.cat(bands)


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
def _sum_by_year(fc, image, scale_m: int, s: int, ts: int):
    import ee

    return image.reduceRegions(collection=fc, reducer=ee.Reducer.sum(),
                               scale=scale_m or s, tileScale=ts).getInfo()


def disturbance_history(p: Point, radii_km: tuple[float, ...] = BUFFER_RADII_KM,
                        mode: BufferMode = "disc") -> tuple[pd.DataFrame, Provenance]:
    """Hansen tree-cover loss by year, area per buffer: ``radius_km, year, class_id, area_ha``
    (one class, 1 = tree-cover loss: the product does not record the cause)."""
    import ee

    get_ee()
    validate_for_analysis(p)
    fc = buffer_collection(p, radii_km, mode)
    g = _hansen()
    forest = _forest2000()
    area_ha = ee.Image.pixelArea().divide(10_000.0)
    bands = []
    for y in cfg.LOSS_YEARS:
        code = y - cfg.LOSS_YEAR_START + 1
        hit = g.select("loss").eq(1).And(forest).And(g.select("lossyear").eq(code))
        bands.append(area_ha.updateMask(hit).rename(f"loss_{y}"))
    image = ee.Image.cat(bands)
    prov = _prov("world_disturbance_history", cfg.HANSEN, [f"loss_{y}" for y in cfg.LOSS_YEARS],
                 "sum", p, radii_km, mode, {"treecover_threshold_pct": fc_cfg.HANSEN_TREECOVER_THRESHOLD,
                                            "cause": "not recorded by the product"})
    stats = _run(prov, lambda s, ts: _sum_by_year(fc, image, 0, s, ts), "Hansen loss history")
    rows: list[dict[str, Any]] = []
    for feat in stats["features"]:
        props = feat["properties"]
        for y in cfg.LOSS_YEARS:
            v = float(props.get(f"loss_{y}") or 0.0)
            if v > 0:
                rows.append({"radius_km": float(props["radius_km"]), "year": y, "class_id": 1, "area_ha": v})
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
    """Forest area per buffer by years since the last tree-cover loss: ``radius_km, bin, area_ha, color``.

    Forest = canopy of at least the threshold in 2000. ``prov.extra["non_tree_ha"]`` carries, per
    radius, the buffer area that was not forest in 2000 (the complement: reported, not dropped).
    """
    get_ee()
    validate_for_analysis(p)
    fc = buffer_collection(p, radii_km, mode)
    image = time_since_image()
    prov = _prov("world_time_since_disturbance", cfg.HANSEN, ["age_bin"], "frequencyHistogram", p, radii_km,
                 mode, {"censored_at": cfg.LOSS_YEAR_START, "reference_year": cfg.LOSS_YEAR_END,
                        "treecover_threshold_pct": fc_cfg.HANSEN_TREECOVER_THRESHOLD})
    hist, areas = _run(prov, _histograms(fc, image, True), "Hansen age")
    px = _px_area(areas)
    rows, non_tree = [], {}
    for feat in hist["features"]:
        props = feat["properties"]; radius = props["radius_km"]; ha_px = px.get(radius, 900.0) / 10_000.0
        h = props.get("histogram") or props.get("age_bin") or {}
        for b, count in h.items():
            label = cfg.AGE_ORDER[int(float(b))]
            rows.append({"radius_km": float(radius), "bin": label, "area_ha": float(count) * ha_px,
                         "color": cfg.AGE_COLORS[label]})
        non_tree[f"{radius:g}"] = None            # filled by the caller from the nominal disc area
    df = pd.DataFrame.from_records(rows, columns=["radius_km", "bin", "area_ha", "color"])
    prov.extra["non_tree_ha"] = non_tree
    return df, prov


def fire_history(p: Point, radii_km: tuple[float, ...] = BUFFER_RADII_KM,
                 mode: BufferMode = "disc") -> tuple[pd.DataFrame, Provenance]:
    """MODIS burned area by year: ``radius_km, year, class_id, area_ha`` (class 1 = burned)."""
    import ee

    get_ee()
    validate_for_analysis(p)
    fc = buffer_collection(p, radii_km, mode)
    area_ha = ee.Image.pixelArea().divide(10_000.0)
    stack = burn_stack()
    image = ee.Image.cat([area_ha.updateMask(stack.select(f"burn_{y}")).rename(f"burn_{y}")
                          for y in cfg.BURN_YEARS])
    prov = _prov("world_fire_history", cfg.MODIS_BURN, [f"burn_{y}" for y in cfg.BURN_YEARS], "sum", p,
                 radii_km, mode, {"scale_m": cfg.BURN_SCALE_M,
                                  "note": "MODIS burned area, 500 m: small fires fall between pixels"})
    stats = _run(prov, lambda s, ts: _sum_by_year(fc, image, cfg.BURN_SCALE_M, s, ts), "MODIS burn history")
    rows: list[dict[str, Any]] = []
    for feat in stats["features"]:
        props = feat["properties"]
        for y in cfg.BURN_YEARS:
            v = float(props.get(f"burn_{y}") or 0.0)
            if v > 0:
                rows.append({"radius_km": float(props["radius_km"]), "year": y, "class_id": 1, "area_ha": v})
    df = pd.DataFrame.from_records(rows, columns=["radius_km", "year", "class_id", "area_ha"])
    if not df.empty:
        df["class_en"] = df["class_id"].map(lambda c: cfg.severity_label(int(c), "en"))
        df["class_pt"] = df["class_id"].map(lambda c: cfg.severity_label(int(c), "pt"))
        df["color"] = df["class_id"].map(lambda c: cfg.SEVERITY_COLORS[int(c)])
        df = df.sort_values(["radius_km", "year", "class_id"]).reset_index(drop=True)
    prov.extra["years_available"] = list(cfg.BURN_YEARS)
    return df, prov


def canopy_history(p: Point, radii_km: tuple[float, ...] = BUFFER_RADII_KM,
                   mode: BufferMode = "disc") -> tuple[pd.DataFrame, Provenance]:
    """Mean tree-canopy cover (%) per buffer and year: ``radius_km, year, canopy_pct`` — Hansen's 2000
    canopy minus the pixels lost by that year (regrowth is not counted)."""
    import ee

    get_ee()
    validate_for_analysis(p)
    fc = buffer_collection(p, radii_km, mode)
    years = list(cfg.CANOPY_YEARS)
    image = canopy_stack(years)
    prov = _prov("world_canopy_history", cfg.HANSEN, [f"canopy_{y}" for y in years], "mean", p, radii_km,
                 mode, {"note": "2000 canopy minus loss to date; regrowth not counted"})

    def call(s, ts):
        return image.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=s,
                                   tileScale=ts).getInfo()
    stats = _run(prov, call, "Hansen canopy history")
    rows = []
    for feat in stats["features"]:
        props = feat["properties"]
        for y in years:
            v = props.get(f"canopy_{y}")
            if v is not None:
                rows.append({"radius_km": float(props["radius_km"]), "year": y, "canopy_pct": round(float(v), 2)})
    return pd.DataFrame.from_records(rows, columns=["radius_km", "year", "canopy_pct"]), prov
