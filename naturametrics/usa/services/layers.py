"""Layer specs for the USA map (lower 48).

Same contract as :mod:`naturametrics.services.layers` — a layer spec is the plain
dict the Leaflet hook diffs on — and the plain-XYZ basemap builder is imported from
there unchanged.

What is American is which Earth Engine images get minted: Annual NLCD for one year,
Hansen tree cover and the Hansen loss/gain mask, and the annual Landsat composites.
There is no stand-age layer: NTEMS is Canadian and the US has no equivalent in the
catalog this page uses. Every image goes through the shared
:func:`~naturametrics.services.tiles.get_tile_url` cache, so switching years costs one
round-trip the first time and nothing after.
"""

from __future__ import annotations

import logging
from typing import Any

from ...services.layers import basemap_spec  # noqa: F401  (re-exported)
from ...services.tiles import get_tile_url
from ..config import nlcd
from ..config import datasets as ds
from ..config import forest as fc_cfg

logger = logging.getLogger(__name__)

LayerSpec = dict[str, Any]

NLCD_ATTRIBUTION = "USGS — Annual National Land Cover Database (Collection 1 v2)"
HANSEN_ATTRIBUTION = "Hansen/UMD/Google/USGS/NASA — Global Forest Change"


def nlcd_spec(year: int, opacity: float = 0.75, z_index: int = 10,
              clip: str | None = None, region: str = "conus") -> LayerSpec | None:
    """Annual NLCD for one year (the nearest snapshot year in Alaska and Hawaii)."""
    from .nlcd_history import nlcd_year_image

    if region in nlcd.NO_LANDCOVER:
        return None
    year = nlcd.nearest_year(region, year)
    cache_id = f"us:nlcd:{year}" if region == "conus" else f"us:nlcd:{region}:{year}"
    url = get_tile_url(cache_id, lambda: nlcd_year_image(year, region), nlcd.NLCD_VIS)
    if url is None:
        return None
    return {
        "id": cache_id,
        "url": url,
        "opacity": opacity,
        "attribution": f"{NLCD_ATTRIBUTION} {year}",
        "z_index": z_index,
        "max_native_zoom": 15,
        "clip": clip,
    }


def tcc_spec(year: int, region: str = "conus", opacity: float = 0.7, z_index: int = 11) -> LayerSpec | None:
    """USFS Tree Canopy Cover for one year (0–100 %)."""
    from .disturbance import tcc_year_image
    from ..config import disturbance as dcfg

    year = min(max(year, dcfg.TCC_YEAR_START), dcfg.TCC_YEAR_END)
    cid = f"us:tcc:{region}:{year}"
    vis = {"min": 0, "max": 100, "palette": ["ffffe5", "d9f0a3", "78c679", "238443", "004529"]}
    url = get_tile_url(cid, lambda: tcc_year_image(region, year).selfMask(), vis)
    if url is None:
        return None
    return {"id": cid, "url": url, "opacity": opacity, "z_index": z_index, "max_native_zoom": 15,
            "attribution": f"USFS GTAC — NLCD Tree Canopy Cover {year}"}


def lcms_loss_spec(region: str = "conus", opacity: float = 0.8, z_index: int = 12) -> LayerSpec | None:
    """Year of the most recent tree-removing disturbance (LCMS), 1985 (pale) to 2025 (dark red)."""
    from .disturbance import last_disturbance_year_image

    cid = f"us:lcms_loss:{region}"
    vis = {"min": 1985, "max": 2025, "palette": ["ffffb2", "fecc5c", "fd8d3c", "e31a1c", "800026"]}
    url = get_tile_url(cid, lambda: last_disturbance_year_image(region), vis)
    if url is None:
        return None
    return {"id": cid, "url": url, "opacity": opacity, "z_index": z_index, "max_native_zoom": 15,
            "attribution": "USFS GTAC — LCMS v2025-11: most recent disturbance year"}


def mtbs_spec(region: str = "conus", opacity: float = 0.8, z_index: int = 13) -> LayerSpec | None:
    """Highest MTBS burn severity seen on each pixel across the record."""
    from .disturbance import mtbs_max_image
    from ..config import disturbance as dcfg

    cid = f"us:mtbs:{region}"
    vis = {"min": 1, "max": 5, "palette": [dcfg.SEVERITY_COLORS[i].lstrip("#") for i in range(1, 6)]}
    url = get_tile_url(cid, lambda: mtbs_max_image(region), vis)
    if url is None:
        return None
    return {"id": cid, "url": url, "opacity": opacity, "z_index": z_index, "max_native_zoom": 15,
            "attribution": "USGS/USFS — MTBS burn severity (highest on record)"}


def hansen_treecover_spec(threshold: int, opacity: float = 0.75,
                          z_index: int = 11) -> LayerSpec | None:
    """Hansen canopy cover in 2000, above the forest threshold."""
    from .forest import hansen_image

    def build():
        gfc = hansen_image()
        return gfc.select("treecover2000").updateMask(
            gfc.select("treecover2000").gte(threshold))

    url = get_tile_url(f"us:hansen_tc:{threshold}", build,
                       fc_cfg.HANSEN_TREECOVER_VIS)
    if url is None:
        return None
    return {
        "id": f"us:hansen_tc:{threshold}",
        "url": url,
        "opacity": opacity,
        "attribution": f"{HANSEN_ATTRIBUTION} — tree cover 2000 (≥{threshold}%)",
        "z_index": z_index,
        "max_native_zoom": 15,
    }


def hansen_change_spec(from_year: int, threshold: int, opacity: float = 0.85,
                       z_index: int = 20) -> LayerSpec | None:
    """Loss (red) and gain (green) since ``from_year``.

    Canada's answer to Brazil's change mask. Loss is filtered by ``lossyear`` so
    the baseline slider works; **gain is not**, because Hansen publishes gain as
    one undated flag for the whole record. Moving the slider therefore changes
    the red and leaves the green alone — stated here and in the panel copy,
    because a control that silently governs only half of what it draws would be
    a trap.
    """
    from .forest import hansen_image

    def build():
        import ee

        gfc = hansen_image()
        forest2000 = gfc.select("treecover2000").gte(threshold)
        code = from_year - fc_cfg.HANSEN_LOSS_YEAR_START + 1
        loss = (gfc.select("loss").eq(1)
                .And(forest2000)
                .And(gfc.select("lossyear").gte(code)))
        gain = gfc.select("gain").eq(1)
        # 1 = loss, 2 = gain. Loss painted second so a pixel flagged both ways
        # reads as loss — the conservative call for a screening layer.
        return (ee.Image(0)
                .where(gain, 2)
                .where(loss, 1)
                .selfMask()
                .rename("change"))

    vis = {"min": 1, "max": 2,
           "palette": [fc_cfg.HANSEN_LOSS_COLOR.lstrip("#"),
                       fc_cfg.HANSEN_GAIN_COLOR.lstrip("#")]}
    url = get_tile_url(f"us:hansen_change:{from_year}:{threshold}", build, vis)
    if url is None:
        return None
    return {
        "id": f"us:hansen_change:{from_year}:{threshold}",
        "url": url,
        "opacity": opacity,
        "attribution": (f"{HANSEN_ATTRIBUTION} — loss {from_year}–"
                        f"{fc_cfg.HANSEN_LOSS_YEAR_END}, gain (undated)"),
        "z_index": z_index,
        "max_native_zoom": 15,
    }


def landsat_spec(key: str, year: int, z_index: int = 0) -> LayerSpec | None:
    """One year of the annual Landsat composite, in the chosen rendering."""
    import ee

    conf = ds.LANDSAT_RENDERINGS.get(key)
    if conf is None:
        logger.warning("Unknown Landsat rendering %r", key)
        return None

    def build():
        col = ee.ImageCollection(ds.LANDSAT_ANNUAL_DATASET)
        return ee.Image(col.filterDate(f"{year}-01-01", f"{year}-12-31").first())

    url = get_tile_url(f"us:landsat:{key}:{year}", build, conf["vis"])
    if url is None:
        return None
    return {
        "id": f"us:landsat:{key}:{year}",
        "url": url,
        "opacity": 1.0,
        "attribution": f"{ds.LANDSAT_ATTRIBUTION} — {year}",
        "z_index": z_index,
        "max_native_zoom": 14,
    }
