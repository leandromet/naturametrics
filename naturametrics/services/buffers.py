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
BufferShape = Literal["circle", "square"]


def _square_geometry(p: Point, side_km: float):
    """Return a metric square centred on ``p`` as an Earth Engine polygon."""
    from pyproj import Transformer

    aeqd = f"+proj=aeqd +lat_0={p.lat} +lon_0={p.lon} +units=m +datum=WGS84 +no_defs"
    to_aeqd = Transformer.from_crs("EPSG:4326", aeqd, always_xy=True).transform
    to_wgs = Transformer.from_crs(aeqd, "EPSG:4326", always_xy=True).transform
    origin = to_aeqd(p.lon, p.lat)
    half = side_km * 1000.0 / 2.0
    corners = [(origin[0] + x, origin[1] + y)
               for x, y in ((-half, -half), (half, -half),
                            (half, half), (-half, half), (-half, -half))]
    coordinates = [to_wgs(x, y) for x, y in corners]
    import ee
    return ee.Geometry.Polygon([coordinates])


def buffer_geometries(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
    shape: BufferShape = "circle",
) -> list[tuple[float, Any]]:
    """Build ``(radius_km, ee.Geometry)`` pairs, smallest first.

    Discs are nested (0→N); rings are the annulus between consecutive radii, so
    the first ring equals the first disc.
    """
    import ee

    centre = p.to_ee_point()
    radii = sorted(radii_km)
    discs = {
        r: (centre.buffer(r * 1000.0) if shape == "circle"
            else _square_geometry(p, r))
        for r in radii
    }

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
    shape: BufferShape = "circle",
):
    """All buffers as one ``ee.FeatureCollection``.

    This is what makes the batched ``reduceRegions`` in
    :mod:`naturametrics.services.mapbiomas_history` a single round-trip rather
    than one per buffer.
    """
    import ee

    return ee.FeatureCollection([
        ee.Feature(geom, {"radius_km": r})
        for r, geom in buffer_geometries(p, radii_km, mode, shape)
    ])


def buffer_geojson(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
    shape: BufferShape = "circle",
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
    geometries = {
        r: (origin.buffer(r * 1000.0, quad_segs=32) if shape == "circle"
            else origin.buffer(r * 1000.0 / 2.0, quad_segs=1))
        for r in radii
    }

    features = [{
        "type": "Feature",
        "geometry": p.to_geojson(),
        "properties": {"role": "study_point", "label": str(p)},
    }]

    for i, r in enumerate(radii):
        geometry = (geometries[r] if (mode == "disc" or i == 0)
                    else geometries[r].difference(geometries[radii[i - 1]]))
        features.append({
            "type": "Feature",
            "geometry": mapping(shp_transform(to_wgs, geometry)),
            "properties": {
                "role": "buffer",
                "radius_km": r,
                "mode": mode,
                "shape": shape,
                "label": f"{r:g} km",
            },
        })

    return {"type": "FeatureCollection", "features": features}


def disc_area_ha(radius_km: float) -> float:
    """Nominal disc area, for sanity-checking measured totals."""
    import math
    return math.pi * (radius_km * 1000.0) ** 2 / 10_000.0


def buffer_circles_geojson(
    points: list[tuple[float, float]],
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    shape: BufferShape = "circle",
) -> dict[str, Any]:
    """Buffer rings for many points, as centres and radii rather than polygons.

    :func:`buffer_geojson` reprojects and tessellates each ring, which is right
    for one point — the outline is exact and it is already on screen before Earth
    Engine answers. For a selection of two hundred it is the wrong shape entirely:
    200 points × 4 rings × 128 vertices is roughly two megabytes of coordinates
    crossing the WebSocket every time the user clicks one more.

    So this emits three numbers per ring and lets Leaflet draw the circle. The
    two differ by Leaflet's projection of a metric radius versus a true azimuthal
    equidistant buffer — a sub-pixel difference at these radii, and neither is
    what is measured: the analysis uses Earth Engine's own geometry either way.
    """
    features: list[dict[str, Any]] = []
    for lat, lon in points:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"role": "selected_point"},
        })
        for radius in sorted(radii_km):
            if shape == "circle":
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {
                        "role": "buffer_circle",
                        "radius_km": radius,
                        "radius_m": radius * 1000.0,
                    },
                })
            else:
                feature = buffer_geojson(
                    Point(lat=lat, lon=lon), (radius,), shape="square"
                )["features"][1]
                feature["properties"]["role"] = "buffer"
                features.append(feature)
    return {"type": "FeatureCollection", "features": features}
