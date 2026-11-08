"""Layer specs for the world map.

Same contract as :mod:`naturametrics.services.layers` — a layer spec is the plain
dict the Leaflet hook diffs on — and the plain-XYZ basemap builder is imported from
there unchanged.

What is global is which Earth Engine images get minted: GLC-FCS30D land cover for one year (in tile
groups, so a first load mints two URLs, not four), Hansen tree cover and the Hansen loss/gain mask,
the year of the last Hansen loss and of the last MODIS burn, and the annual Landsat composites.
There is no stand-age layer: NTEMS is Canadian. Every image goes through the shared
:func:`~naturametrics.services.tiles.get_tile_url` cache, so switching years costs one
round-trip the first time and nothing after.
"""

from __future__ import annotations

import logging
from typing import Any

from ...services.layers import basemap_spec  # noqa: F401  (re-exported)
from ...services.tiles import get_tile_url
from ..config import glc
from ..config import datasets as ds
from ..config import forest as fc_cfg
from ..config import disturbance as dcfg
from . import glc_earth

logger = logging.getLogger(__name__)

LayerSpec = dict[str, Any]

GLC_ATTRIBUTION = "GLC-FCS30D annual land cover (Zhang et al. 2021, ESSD 13)"
HANSEN_ATTRIBUTION = "Hansen/UMD/Google/USGS/NASA — Global Forest Change"

#: The four tile groups (west, south, east, north) and the two the page opens with.
GROUPS = glc_earth.GROUPS
START_GROUPS = glc_earth.START_GROUPS


def glc_lid(year: int, group: str) -> str:
    return f"world:glc:{year}:{group}"


def glc_spec(year: int, group: str, opacity: float = 0.75, z_index: int = 10,
             clip: str | None = None) -> LayerSpec | None:
    """GLC-FCS30D for one year and one tile group (sea water hidden, continental water kept)."""
    year = glc.nearest_year("world", year)
    url = glc_earth.tile_url(group, year, GROUPS[group])
    if url is None:
        return None
    return {
        "id": glc_lid(year, group),
        "url": url,
        "opacity": opacity,
        "attribution": f"{GLC_ATTRIBUTION} {year}",
        "z_index": z_index,
        "max_native_zoom": 15,
        "clip": clip,
    }


def loss_year_spec(opacity: float = 0.8, z_index: int = 12) -> LayerSpec | None:
    """Year of the most recent tree-cover loss (Hansen), 2001 (pale) to 2025 (dark red)."""
    from .disturbance import last_disturbance_year_image

    cid = "world:loss_year"
    vis = {"min": dcfg.LOSS_YEAR_START, "max": dcfg.LOSS_YEAR_END,
           "palette": ["ffffb2", "fecc5c", "fd8d3c", "e31a1c", "800026"]}
    url = get_tile_url(cid, last_disturbance_year_image, vis)
    if url is None:
        return None
    return {"id": cid, "url": url, "opacity": opacity, "z_index": z_index, "max_native_zoom": 15,
            "attribution": f"{HANSEN_ATTRIBUTION} — most recent tree-cover loss year"}


def burn_spec(opacity: float = 0.8, z_index: int = 13) -> LayerSpec | None:
    """Year of the most recent burn seen by MODIS (MCD64A1, 500 m), 2001 (pale) to 2025 (dark)."""
    from .disturbance import burn_last_year_image

    cid = "world:burn_year"
    vis = {"min": dcfg.BURN_YEAR_START, "max": dcfg.BURN_YEAR_END,
           "palette": ["fff5eb", "fdd0a2", "fd8d3c", "d94801", "7f2704"]}
    url = get_tile_url(cid, burn_last_year_image, vis)
    if url is None:
        return None
    return {"id": cid, "url": url, "opacity": opacity, "z_index": z_index, "max_native_zoom": 12,
            "attribution": "NASA — MODIS MCD64A1 burned area: most recent burn year"}


def hansen_treecover_spec(threshold: int, opacity: float = 0.75,
                          z_index: int = 11) -> LayerSpec | None:
    """Hansen canopy cover in 2000, above the forest threshold."""
    from .forest import hansen_image

    def build():
        gfc = hansen_image()
        return gfc.select("treecover2000").updateMask(
            gfc.select("treecover2000").gte(threshold))

    url = get_tile_url(f"world:hansen_tc:{threshold}", build,
                       fc_cfg.HANSEN_TREECOVER_VIS)
    if url is None:
        return None
    return {
        "id": f"world:hansen_tc:{threshold}",
        "url": url,
        "opacity": opacity,
        "attribution": f"{HANSEN_ATTRIBUTION} — tree cover 2000 (≥{threshold}%)",
        "z_index": z_index,
        "max_native_zoom": 15,
    }


def hansen_change_spec(from_year: int, threshold: int, opacity: float = 0.85,
                       z_index: int = 20) -> LayerSpec | None:
    """Loss (red) and gain (green) since ``from_year``.

    The same change mask as the other pages. Loss is filtered by ``lossyear`` so
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
    url = get_tile_url(f"world:hansen_change:{from_year}:{threshold}", build, vis)
    if url is None:
        return None
    return {
        "id": f"world:hansen_change:{from_year}:{threshold}",
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

    url = get_tile_url(f"world:landsat:{key}:{year}", build, conf["vis"])
    if url is None:
        return None
    return {
        "id": f"world:landsat:{key}:{year}",
        "url": url,
        "opacity": 1.0,
        "attribution": f"{ds.LANDSAT_ATTRIBUTION} — {year}",
        "z_index": z_index,
        "max_native_zoom": 14,
    }
