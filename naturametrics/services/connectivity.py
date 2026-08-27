"""Fragment-to-fragment connectivity — the costly proxy.

``services.landscape_metrics`` always computes ``meff_ha`` (effective mesh
size), a connectivity/fragmentation proxy that is essentially free: it reuses
the connected-components image already built for ``largest_patch_ha``.

The metric people usually mean by "connectivity between fragments" —
FRAGSTATS' mean Euclidean nearest-neighbour distance (ENN_MN) — is a
different, pricier computation. It needs *true* patch-to-patch distance, and
Earth Engine has no polygon-to-polygon nearest-neighbour join at fragment
scale. So this module:

1. Vectorises each buffer's forest pixels into patch polygons with one
   ``reduceToVectors`` call (an Earth Engine round-trip landscape_metrics does
   not need at all).
2. Brings those polygons home and finds each one's nearest same-radius
   neighbour **locally**, with a shapely ``STRtree`` — Earth Engine has
   nothing built for this, and reprojecting first to a local planar (AEQD)
   CRS means "nearest" means actual metres, not degrees.

That is a second Earth Engine call plus a local geometry search per buffer,
against landscape_metrics' one call reusing an already-built image — costly
enough that this is never folded into the automatic ``run_analysis`` fetch.
It lives behind its own button (state.run_connectivity), same reasoning as
``full_area`` sitting behind its own explicit action.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..config import mapbiomas as mb
from ..config.settings import (
    BUFFER_RADII_KM, EE_DEFAULT_SCALE_M, EE_MAX_PIXELS, EE_TILE_SCALE,
)
from .buffers import BufferMode, BufferShape, buffer_geometries
from .ee_client import get_ee
from .geo import Point, validate_for_analysis
from .provenance import Provenance

logger = logging.getLogger(__name__)

#: One row per buffer radius.
CONNECTIVITY_COLUMNS = ["radius_km", "n_fragments", "enn_mean_m", "enn_median_m"]

#: Fragments smaller than this are classification slivers, not fragments
#: anyone means by "connectivity between fragments" — mirrors the judgement
#: call already made for the patch-size cap in landscape_metrics.py.
MIN_FRAGMENT_PIXELS = 9

#: Hard ceiling on how many fragments the nearest-neighbour search runs over,
#: per radius. A heavily fragmented 20 km buffer can hold thousands of forest
#: patches; vectorising and shipping all of them home, then building an
#: STRtree over them, is exactly the cost this feature exists to let a user
#: opt into — but an unbounded fetch can still turn "slower" into "the
#: request never returns". Capped rather than refused: the result still
#: reports what it saw, marked degraded (Provenance.degrade), same posture
#: as buffer_estimate in services/exports.py.
MAX_FRAGMENTS_PER_RADIUS = 600


def _forest_mask(image):
    codes = sorted(mb.FOREST_FORMATIONS)
    return image.remap(codes, [1] * len(codes), 0).selfMask().rename("forest")


def fragment_connectivity(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
    shape: BufferShape = "circle",
    year: int = mb.MAPBIOMAS_YEAR_END,
    max_fragments: int = MAX_FRAGMENTS_PER_RADIUS,
) -> tuple[pd.DataFrame, Provenance]:
    """Mean/median Euclidean nearest-neighbour distance between forest
    fragments (:data:`mb.FOREST_FORMATIONS`), per buffer radius.

    Distance is edge-to-edge between fragment *polygons* (not centroids —
    centroid distance is a poor stand-in for irregular, elongated raster
    patches), measured on a local azimuthal-equidistant projection centred on
    ``p`` so that "metres" means metres.
    """
    import ee
    from pyproj import Transformer
    from shapely.geometry import shape as shp_shape
    from shapely.ops import transform as shp_transform
    from shapely.strtree import STRtree

    get_ee()
    validate_for_analysis(p)

    image = ee.Image(mb.MAPBIOMAS_COLLECTIONS[mb.MAPBIOMAS_DEFAULT_COLLECTION]).select(
        mb.band_for_year(year)).rename("class")
    forest = _forest_mask(image)

    aeqd = f"+proj=aeqd +lat_0={p.lat} +lon_0={p.lon} +units=m +datum=WGS84 +no_defs"
    to_aeqd = Transformer.from_crs("EPSG:4326", aeqd, always_xy=True).transform
    min_area_m2 = MIN_FRAGMENT_PIXELS * (EE_DEFAULT_SCALE_M ** 2)

    records: list[dict[str, Any]] = []
    degraded_radii: list[float] = []

    for radius, geom in buffer_geometries(p, radii_km, mode, shape):
        vectors = forest.reduceToVectors(
            geometry=geom, scale=EE_DEFAULT_SCALE_M, geometryType="polygon",
            eightConnected=True, maxPixels=EE_MAX_PIXELS, tileScale=EE_TILE_SCALE,
        )
        # +1 so a count of exactly max_fragments+1 still reads as "capped"
        # rather than silently passing as "all of them".
        info = vectors.limit(max_fragments + 1).getInfo()
        features = info.get("features", [])
        capped = len(features) > max_fragments
        if capped:
            features = features[:max_fragments]
            degraded_radii.append(radius)

        polys_m = []
        for feat in features:
            geom_m = shp_transform(to_aeqd, shp_shape(feat["geometry"]))
            if geom_m.area >= min_area_m2:
                polys_m.append(geom_m)

        n = len(polys_m)
        if n < 2:
            records.append({"radius_km": radius, "n_fragments": n,
                            "enn_mean_m": None, "enn_median_m": None})
            continue

        tree = STRtree(polys_m)
        distances = []
        for geom_m in polys_m:
            idx, dist = tree.query_nearest(
                geom_m, exclusive=True, return_distance=True, all_matches=False)
            if len(idx):
                distances.append(float(dist[0]))
        if not distances:
            records.append({"radius_km": radius, "n_fragments": n,
                            "enn_mean_m": None, "enn_median_m": None})
            continue

        series = pd.Series(distances)
        records.append({
            "radius_km": radius, "n_fragments": n,
            "enn_mean_m": float(series.mean()),
            "enn_median_m": float(series.median()),
        })

    # Built from a plain list of records (not assembled column-by-column), so
    # a None next to real floats in the same column becomes pandas NaN — and
    # this frame reaches Reflex state as JSON, where NaN is not a legal
    # value. Swap it back to None (object dtype is fine at four columns and a
    # handful of rows) rather than have the frontend choke on a malformed
    # payload the one time a buffer holds fewer than two fragments.
    df = pd.DataFrame.from_records(records, columns=CONNECTIVITY_COLUMNS)
    df = df.where(pd.notnull(df), None)

    prov = Provenance(
        name="fragment_connectivity",
        dataset_id=mb.MAPBIOMAS_COLLECTIONS[mb.MAPBIOMAS_DEFAULT_COLLECTION],
        bands=[mb.band_for_year(year)],
        scale_m=EE_DEFAULT_SCALE_M,
        reducer="reduceToVectors + local nearest-neighbour (shapely STRtree)",
        pixel_area_basis="n/a — vector polygons, planar AEQD metres",
        max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE,
        geometry=p.to_geojson(),
        extra={
            "year": year, "buffer_mode": mode, "buffer_shape": shape,
            "radii_km": list(radii_km), "point": str(p),
            "forest_classes": sorted(mb.FOREST_FORMATIONS),
            "min_fragment_pixels": MIN_FRAGMENT_PIXELS,
            "max_fragments_per_radius": max_fragments,
        },
    )
    if degraded_radii:
        prov.degrade(
            f"Raio(s) {', '.join(f'{r:g} km' for r in sorted(degraded_radii))} "
            f"tinham mais de {max_fragments} fragmentos de floresta; a "
            f"distância ao vizinho mais próximo considerou só os primeiros "
            f"{max_fragments} retornados pelo Earth Engine, não a totalidade."
        )
    logger.info("Fragment connectivity for %s: %s radii (%s degraded)", p,
               len(df), len(degraded_radii))
    return df, prov
