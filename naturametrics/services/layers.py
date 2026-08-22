"""Layer specs handed to the map component.

A "layer spec" is a plain dict the Leaflet hook understands:

    {"id": str, "url": str, "opacity": float, "attribution": str,
     "z_index": int, "max_native_zoom": int}

``id`` is the diff key — the hook adds, updates or removes layers by comparing
these against what is already on the map, so ids must be stable across renders
and must change when the pixels change.

Two more layers build their own specs, in the modules that own their data:
:mod:`naturametrics.services.ifn` (the IFN point grid and its filters) and
:mod:`naturametrics.services.biomes` (IBGE biomes, which are drawn in the
browser rather than tiled — see that module for why).
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import datasets as ds
from ..config import mapbiomas as mb
from ..config import settings as st
from .tiles import get_tile_url

logger = logging.getLogger(__name__)

LayerSpec = dict[str, Any]


def basemap_spec(key: str, z_index: int = 0) -> LayerSpec | None:
    """Plain XYZ basemap — no Earth Engine involved, so this never fails slowly.

    Earth-Engine-backed basemaps go through :func:`ee_basemap_spec` instead; this
    function stays synchronous and infallible precisely so that the very first
    paint never waits on a network call (see the seeding comment in
    ``state/_layers.py``).
    """
    conf = ds.BASEMAPS.get(key)
    if conf is None:
        logger.warning("Unknown XYZ basemap %r", key)
        return None
    return {
        "id": f"basemap:{key}",
        "url": conf["url"],
        "opacity": 1.0,
        "attribution": conf["attribution"],
        "z_index": z_index,
        "max_native_zoom": conf.get("max_native_zoom", 19),
    }


def ee_basemap_spec(key: str, z_index: int = 0) -> LayerSpec | None:
    """Mint an Earth Engine basemap (the SPOT 2008 mosaics).

    Blocking, so callers run it off the event loop. Cached like every other tile
    URL, so switching back and forth costs one round-trip in total.
    """
    conf = ds.EE_BASEMAPS.get(key)
    if conf is None:
        logger.warning("Unknown Earth Engine basemap %r", key)
        return None

    def build():
        import ee
        return ee.Image(conf["asset"])

    url = get_tile_url(f"basemap:{key}", build, conf["vis"])
    if url is None:
        return None

    return {
        "id": f"basemap:{key}",
        "url": url,
        "opacity": 1.0,
        "attribution": conf["attribution"],
        "z_index": z_index,
        "max_native_zoom": conf.get("max_native_zoom", 16),
    }


def mapbiomas_spec(
    year: int,
    opacity: float = 0.75,
    collection: str = mb.MAPBIOMAS_DEFAULT_COLLECTION,
    z_index: int = 10,
) -> LayerSpec | None:
    """MapBiomas land cover for one year.

    The cache key carries the collection version and the year, which is
    everything that changes the pixels for this layer.
    """
    if year not in mb.MAPBIOMAS_YEARS:
        logger.warning("MapBiomas year %s outside %s–%s",
                       year, mb.MAPBIOMAS_YEAR_START, mb.MAPBIOMAS_YEAR_END)
        return None

    asset = mb.MAPBIOMAS_COLLECTIONS[collection]
    cache_key = f"mapbiomas:{collection}:{year}"

    def build():
        import ee
        return ee.Image(asset).select(mb.band_for_year(year))

    url = get_tile_url(cache_key, build, mb.MAPBIOMAS_VIS)
    if url is None:
        return None

    return {
        "id": cache_key,
        "url": url,
        "opacity": opacity,
        "attribution": f"MapBiomas Collection {collection.replace('v', '').replace('_', '.')}",
        "z_index": z_index,
        "max_native_zoom": 15,
    }


def prefetch_mapbiomas_years(
    years: list[int] | None = None,
    collection: str = mb.MAPBIOMAS_DEFAULT_COLLECTION,
    skip: set[int] | None = None,
) -> dict[int, str | None]:
    """Warm the tile-URL cache for many years at once, concurrently.

    This is the speculative prefetch from doc/06-ee-layers.md §5b, and it is what
    makes the year slider instant. Measured: 40 years in ~1.4 s against ~21 s
    serial. Under the Partner tier minting URLs the user may never look at costs
    nothing meaningful.

    Args:
        skip: years already cached, not re-minted. Lets a caller run the sweep in
            priority order without paying twice for the overlap.
    """
    from .ee_concurrency import get_ee_executor

    years = years or mb.MAPBIOMAS_YEARS
    skip = skip or set()
    todo = [y for y in years if y not in skip]
    if not todo:
        return {}

    executor = get_ee_executor()
    futures = {
        year: executor.submit(mapbiomas_spec, year, 0.75, collection)
        for year in todo
    }

    results: dict[int, str | None] = {}
    for year, future in futures.items():
        try:
            spec = future.result(timeout=120)
            results[year] = spec["url"] if spec else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Prefetch failed for %s: %s", year, exc)
            results[year] = None

    ok = sum(1 for v in results.values() if v)
    logger.info("Prefetched %s/%s MapBiomas tile URLs", ok, len(results))
    return results


def prefetch_window(
    around: int,
    radius: int = 5,
    collection: str = mb.MAPBIOMAS_DEFAULT_COLLECTION,
) -> dict[int, str | None]:
    """Mint just the years near ``around``.

    Run before the full sweep so the first slider movements are instant even on a
    cold instance, where the whole 40-year set has not landed yet.
    """
    lo = max(mb.MAPBIOMAS_YEAR_START, around - radius)
    hi = min(mb.MAPBIOMAS_YEAR_END, around + radius)
    return prefetch_mapbiomas_years(list(range(lo, hi + 1)), collection)


def ibge_vegetation_spec(opacity: float = 0.6, z_index: int = 13) -> LayerSpec | None:
    """IBGE Vegetação 2022 (services.ibge_vegetation), rasterized from its
    145,458-feature source asset once per mint via ``reduceToImage`` — a single
    snapshot, so unlike MapBiomas/biomass there is no year key, and unlike
    services.biomes this never leaves Earth Engine as browser-side geometry."""
    from .ibge_vegetation import _classified_image
    from ..config.ibge_vegetation import IBGE_VEG_ATTRIBUTION, IBGE_VEG_VIS

    cache_key = "ibge_vegetation:leg2"

    def build():
        return _classified_image()

    url = get_tile_url(cache_key, build, IBGE_VEG_VIS)
    if url is None:
        return None

    return {
        "id": cache_key,
        "url": url,
        "opacity": opacity,
        "attribution": IBGE_VEG_ATTRIBUTION,
        "z_index": z_index,
        "max_native_zoom": 13,
    }


def biomass_spec(year: int, opacity: float = 0.75, z_index: int = 14) -> LayerSpec | None:
    """ESA CCI Biomass_cci above-ground biomass for one year.

    Ten non-contiguous years (services.biomass.AGB_YEARS) rather than a
    continuous range, so unlike MapBiomas this is never worth a startup
    prefetch sweep — it is opt-in and minted on demand the first time the
    layer (or a new year on it) is switched on.
    """
    from .biomass import AGB_ASSET_TEMPLATE, AGB_VIS, AGB_YEARS

    if year not in AGB_YEARS:
        logger.warning("Biomass year %s not in %s", year, AGB_YEARS)
        return None

    cache_key = f"biomass:{year}"

    def build():
        import ee
        return ee.Image(AGB_ASSET_TEMPLATE.format(year=year)).select("agb")

    url = get_tile_url(cache_key, build, AGB_VIS)
    if url is None:
        return None

    return {
        "id": cache_key,
        "url": url,
        "opacity": opacity,
        "attribution": "ESA CCI Biomass_cci v6.0 (Santoro & Cartus, 2025)",
        "z_index": z_index,
        # 100 m native resolution — coarser than MapBiomas' 30 m, so tiles
        # stop being real detail a couple of zoom levels sooner.
        "max_native_zoom": 13,
    }


# --------------------------------------------------------------------------- #
# Hansen Global Forest Change — ported from the Canada page's
# canada/services/layers.py (same asset, same visualization) so both pages
# agree on what a "forest" pixel is (config.datasets.HANSEN_GFC).
# --------------------------------------------------------------------------- #

def hansen_treecover_spec(
    threshold: int = st.HANSEN_TREECOVER_THRESHOLD,
    opacity: float = 0.6,
    z_index: int = 15,
) -> LayerSpec | None:
    """Tree cover in 2000, masked at the chosen canopy-cover threshold.

    The threshold changes which pixels are painted at all, not just their
    colour: below it, a pixel is not "forest" for this layer's purposes.
    """
    cache_key = f"hansen_tc:{threshold}"

    def build():
        import ee
        gfc = ee.Image(ds.HANSEN_GFC["asset"])
        treecover = gfc.select("treecover2000")
        return treecover.updateMask(treecover.gte(threshold))

    url = get_tile_url(cache_key, build, ds.HANSEN_GFC["treecover_vis"])
    if url is None:
        return None

    return {
        "id": cache_key,
        "url": url,
        "opacity": opacity,
        "attribution": (f"{ds.HANSEN_GFC['attribution']} — cobertura arbórea "
                        f"2000 (≥{threshold}%)"),
        "z_index": z_index,
        "max_native_zoom": 13,
    }


def hansen_change_spec(
    from_year: int,
    threshold: int = st.HANSEN_TREECOVER_THRESHOLD,
    opacity: float = 0.85,
    z_index: int = 16,
) -> LayerSpec | None:
    """Loss since ``from_year`` (red) and gain (green, undated), as one
    categorical band — 1 = loss, 2 = gain, loss painted last so a pixel
    flagged both ways reads as loss.

    Loss is gated by the same canopy threshold as the tree-cover layer (a
    pixel that was never "forest" cannot lose it); gain is **not** — Hansen
    publishes gain as one undated flag for the whole record, with no year
    and no canopy percentage to threshold against, so gating it on the 2000
    tree-cover mask would silently hide regrowth on land that was below the
    threshold in 2000 precisely because it was cleared before then.
    """
    year_start = ds.HANSEN_GFC["loss_year_start"]
    year_end = ds.HANSEN_GFC["loss_year_end"]
    if not (year_start <= from_year <= year_end):
        logger.warning("Hansen loss year %s outside %s–%s",
                       from_year, year_start, year_end)
        return None

    cache_key = f"hansen_change:{from_year}:{threshold}"

    def build():
        import ee
        gfc = ee.Image(ds.HANSEN_GFC["asset"])
        forest2000 = gfc.select("treecover2000").gte(threshold)
        code = from_year - year_start + 1
        loss = (gfc.select("loss").eq(1).And(forest2000)
                .And(gfc.select("lossyear").gte(code)))
        gain = gfc.select("gain").eq(1)
        return ee.Image(0).where(gain, 2).where(loss, 1).selfMask().rename("change")

    vis = {"min": 1, "max": 2,
           "palette": [ds.HANSEN_GFC["loss_color"].lstrip("#"),
                       ds.HANSEN_GFC["gain_color"].lstrip("#")]}
    url = get_tile_url(cache_key, build, vis)
    if url is None:
        return None

    return {
        "id": cache_key,
        "url": url,
        "opacity": opacity,
        "attribution": (f"{ds.HANSEN_GFC['attribution']} — perda "
                        f"{from_year}–{year_end}, ganho (não datado)"),
        "z_index": z_index,
        "max_native_zoom": 13,
    }
