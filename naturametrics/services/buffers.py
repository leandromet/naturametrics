"""Buffer geometries around a study point.

Decision **D2**: cumulative **discs** are the default — "everything within N km"
is what a user means by "a 5 km buffer around this point". Non-overlapping
**rings** are available as a toggle for distance-decay work. The two give
substantially different numbers, so whichever is active is recorded in the
provenance and shown on the chart.

Yvynation buffers outward from a territory *polygon* and therefore uses external
rings exclusively; that reasoning does not carry to a point, which is why this
module differs from its ``buffer_utils``.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from ..config.settings import BUFFER_RADII_KM
from .geo import Point

logger = logging.getLogger(__name__)

BufferMode = Literal["disc", "ring"]


def buffer_geometries(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
) -> list[tuple[float, Any]]:
    """Build ``(radius_km, ee.Geometry)`` pairs, smallest first.

    Discs are nested (0→N); rings are the annulus between consecutive radii, so
    the first ring equals the first disc.
    """
    import ee

    centre = p.to_ee_point()
    radii = sorted(radii_km)
    discs = {r: centre.buffer(r * 1000.0) for r in radii}

    out: list[tuple[float, Any]] = []
    for i, r in enumerate(radii):
        if mode == "disc" or i == 0:
            out.append((r, discs[r]))
        else:
            out.append((r, discs[r].difference(discs[radii[i - 1]], maxError=1)))
    return out


def buffer_collection(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
):
    """All buffers as one ``ee.FeatureCollection``.

    This is what makes the batched ``reduceRegions`` in
    :mod:`naturametrics.services.mapbiomas_history` a single round-trip rather
    than one per buffer.
    """
    import ee

    return ee.FeatureCollection([
        ee.Feature(geom, {"radius_km": r})
        for r, geom in buffer_geometries(p, radii_km, mode)
    ])


def buffer_geojson(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
    max_error_m: float = 50.0,
) -> dict[str, Any]:
    """Buffer outlines as GeoJSON, for drawing on the map.

    Computed **locally** with pyproj + shapely, not via Earth Engine. The rings
    must appear the instant the user clicks (doc/07-ui-ux.md §2); waiting on a
    network round-trip to draw a circle would make the app feel broken. The EE
    geometries used for analysis come from the same centre and radii, so the two
    agree to within the projection error noted below.
    """
    from pyproj import Transformer
    from shapely.geometry import mapping
    from shapely.ops import transform as shp_transform
    from shapely.geometry import Point as ShpPoint

    # Azimuthal equidistant centred on the point: distances from the centre are
    # true, which is exactly what a buffer radius means.
    aeqd = f"+proj=aeqd +lat_0={p.lat} +lon_0={p.lon} +units=m +datum=WGS84 +no_defs"
    to_aeqd = Transformer.from_crs("EPSG:4326", aeqd, always_xy=True).transform
    to_wgs = Transformer.from_crs(aeqd, "EPSG:4326", always_xy=True).transform

    origin = shp_transform(to_aeqd, ShpPoint(p.lon, p.lat))
    radii = sorted(radii_km)
    discs = {r: origin.buffer(r * 1000.0, quad_segs=32) for r in radii}

    features = [{
        "type": "Feature",
        "geometry": p.to_geojson(),
        "properties": {"role": "study_point", "label": str(p)},
    }]

    for i, r in enumerate(radii):
        shape = discs[r] if (mode == "disc" or i == 0) else discs[r].difference(discs[radii[i - 1]])
        features.append({
            "type": "Feature",
            "geometry": mapping(shp_transform(to_wgs, shape)),
            "properties": {
                "role": "buffer",
                "radius_km": r,
                "mode": mode,
                "label": f"{r:g} km",
            },
        })

    return {"type": "FeatureCollection", "features": features}


def disc_area_ha(radius_km: float) -> float:
    """Nominal disc area, for sanity-checking measured totals."""
    import math
    return math.pi * (radius_km * 1000.0) ** 2 / 10_000.0
