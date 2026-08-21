"""Layer specs for the Canada map.

Same contract as :mod:`naturametrics.services.layers` — a layer spec is the
plain dict the Leaflet hook diffs on — and the plain-XYZ basemap builder is
imported from there unchanged rather than copied.

What is Canadian is which Earth Engine images get minted: the ACI classification
for one year, the NTEMS age raster, Hansen tree cover and the Hansen loss/gain
mask, and the annual Landsat composites that stand in for Brazil's SPOT mosaics.
Every one of them goes through the shared :func:`~naturametrics.services.tiles.get_tile_url`
cache, so switching years costs one round-trip the first time and nothing after.
"""

from __future__ import annotations

import logging
from typing import Any

from ...services.layers import basemap_spec  # noqa: F401  (re-exported)
from ...services.tiles import get_tile_url
from ..config import aafc
from ..config import datasets as ds
from ..config import forest as fc_cfg

logger = logging.getLogger(__name__)

LayerSpec = dict[str, Any]

ACI_ATTRIBUTION = "Agriculture and Agri-Food Canada — Annual Crop Inventory"
NTEMS_ATTRIBUTION = "NRCan / NFIS — NTEMS Canada forest age (2019)"
HANSEN_ATTRIBUTION = "Hansen/UMD/Google/USGS/NASA — Global Forest Change"


def aci_spec(year: int, opacity: float = 0.75, z_index: int = 10,
             clip: str | None = None) -> LayerSpec | None:
    """AAFC Annual Crop Inventory for one year."""
    from .aci_history import aci_year_image

    url = get_tile_url(f"ca:aci:{year}", lambda: aci_year_image(year), aafc.ACI_VIS)
    if url is None:
        return None
    return {
        "id": f"ca:aci:{year}",
        "url": url,
        "opacity": opacity,
        "attribution": f"{ACI_ATTRIBUTION} {year}",
        "z_index": z_index,
        "max_native_zoom": 15,
        "clip": clip,
    }


def forest_age_spec(opacity: float = 0.75, z_index: int = 12) -> LayerSpec | None:
    """NTEMS stand age. One image, no year parameter — it is a 2019 snapshot."""
    from .forest import ntems_age_image

    url = get_tile_url(
        "ca:ntems_age",
        lambda: ntems_age_image().select(fc_cfg.NTEMS_AGE_BAND),
        fc_cfg.NTEMS_AGE_VIS,
    )
    if url is None:
        return None
    return {
        "id": "ca:ntems_age",
        "url": url,
        "opacity": opacity,
        "attribution": NTEMS_ATTRIBUTION,
        "z_index": z_index,
        "max_native_zoom": 15,
    }


def hansen_treecover_spec(threshold: int, opacity: float = 0.75,
                          z_index: int = 11) -> LayerSpec | None:
    """Hansen canopy cover in 2000, above the forest threshold."""
    from .forest import hansen_image

    def build():
        gfc = hansen_image()
        return gfc.select("treecover2000").updateMask(
            gfc.select("treecover2000").gte(threshold))

    url = get_tile_url(f"ca:hansen_tc:{threshold}", build,
                       fc_cfg.HANSEN_TREECOVER_VIS)
    if url is None:
        return None
    return {
        "id": f"ca:hansen_tc:{threshold}",
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
    url = get_tile_url(f"ca:hansen_change:{from_year}:{threshold}", build, vis)
    if url is None:
        return None
    return {
        "id": f"ca:hansen_change:{from_year}:{threshold}",
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

    url = get_tile_url(f"ca:landsat:{key}:{year}", build, conf["vis"])
    if url is None:
        return None
    return {
        "id": f"ca:landsat:{key}:{year}",
        "url": url,
        "opacity": 1.0,
        "attribution": f"{ds.LANDSAT_ATTRIBUTION} — {year}",
        "z_index": z_index,
        "max_native_zoom": 14,
    }
