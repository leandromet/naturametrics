"""A user-supplied study region: drawn on the map, pasted as WKT, or uploaded
as a KML file.

Every point-based analysis in this app buffers a :class:`~.geo.Point` into
circles/squares and reduces over them (``services/buffers.py``). A region is
the same idea with one difference: the shape comes from the user instead of
from a radius. It still has to end up as exactly what
``mapbiomas_history._history_from_collection`` and its four siblings already
expect — a single-feature ``ee.FeatureCollection`` with a ``radius_km``
property — because that is the generic reducing code every ``full_area_*``
function already calls; multi-selection's "área total" mode proved a rectangle
works there; an arbitrary polygon works exactly the same way.

**Safety.** A KML file is the one place in this app that accepts an uploaded
file rather than typed/pasted text (``services/user_points.py`` explains why
that was avoided for coordinate lists). ``defusedxml`` is used instead of the
stdlib parser specifically to block XML-entity expansion ("billion laughs")
attacks, and only ``Placemark``/``Polygon``/``outerBoundaryIs``/
``innerBoundaryIs``/``coordinates`` elements are ever read — everything else
in the file (styles, scripts, extended data, network links) is ignored, never
executed.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config.settings import (
    BRAZIL_BBOX, GEOMETRY_KML_MAX_BYTES, GEOMETRY_MAX_AREA_KM2,
    GEOMETRY_MAX_VERTICES, GEOMETRY_REGION_RADIUS_KM,
)

logger = logging.getLogger(__name__)


class GeometryError(ValueError):
    """A region geometry that cannot be used for analysis, with a user-facing reason."""


#: Fallback wording if a caller does not pass ``messages`` — same convention as
#: services/geo.py's _DEFAULT_MESSAGES, kept in sync with translations/pt.py
#: and translations/en.py's matching keys.
_DEFAULT_MESSAGES = {
    "err_geometry_invalid": "A geometria informada não é válida.",
    "err_geometry_empty": "A geometria informada está vazia.",
    "err_geometry_outside_brazil": (
        "A área informada está fora do Brasil. O MapBiomas cobre apenas o "
        "Brasil, portanto não há histórico de cobertura do solo para esta região."
    ),
    "err_geometry_too_large": (
        "A área informada ({area_km2:.0f} km²) excede o limite de "
        "{max_km2:.0f} km²."
    ),
    "err_geometry_too_complex": (
        "O contorno tem {n} vértices, acima do limite de {max_n}."
    ),
    "err_wkt_parse": "Não foi possível interpretar o WKT: {exc}",
    "err_wkt_not_polygon": "O WKT precisa descrever um Polygon ou MultiPolygon.",
    "err_kml_too_large": (
        "O arquivo KML excede o limite de {max_mb:.1f} MB."
    ),
    "err_kml_parse": "Não foi possível interpretar o arquivo KML: {exc}",
    "err_kml_no_polygon": "Nenhum polígono foi encontrado no arquivo KML.",
}


def _tr(messages: dict[str, str] | None, key: str, **kwargs: Any) -> str:
    table = messages or _DEFAULT_MESSAGES
    template = table.get(key, _DEFAULT_MESSAGES[key])
    return template.format(**kwargs)


# --------------------------------------------------------------------------- #
# Building a shapely geometry from each input source
# --------------------------------------------------------------------------- #

def polygon_from_geojson(geojson: dict[str, Any]) -> Any:
    """A shapely geometry from GeoJSON — what leaflet-draw's ``toGeoJSON()``
    emits (a Feature wrapping a Polygon, but bare geometries are accepted too,
    since that is what a hand-built payload might send)."""
    from shapely.geometry import shape

    body = geojson.get("geometry", geojson) if isinstance(geojson, dict) else geojson
    try:
        geom = shape(body)
    except Exception as exc:  # noqa: BLE001
        raise GeometryError(_DEFAULT_MESSAGES["err_geometry_invalid"]) from exc
    return geom


def parse_wkt(text: str, messages: dict[str, str] | None = None) -> Any:
    """A shapely geometry from pasted WKT text."""
    from shapely import wkt as shapely_wkt

    try:
        geom = shapely_wkt.loads(text.strip())
    except Exception as exc:  # noqa: BLE001
        raise GeometryError(_tr(messages, "err_wkt_parse", exc=exc)) from exc
    if geom.geom_type not in ("Polygon", "MultiPolygon"):
        raise GeometryError(_tr(messages, "err_wkt_not_polygon"))
    return geom


def _kml_localname(tag: str) -> str:
    """Strip the namespace off an ElementTree tag — KML ships as 2.1, 2.2 or
    (rarely) no namespace at all, and this app has no reason to care which."""
    return tag.rsplit("}", 1)[-1]


def _kml_ring_coords(ring_elem: Any) -> list[tuple[float, float]]:
    """``outerBoundaryIs``/``innerBoundaryIs`` -> ``LinearRing`` -> ``coordinates``
    text ("lon,lat[,alt] lon,lat[,alt] ...") -> a list of (lon, lat) pairs."""
    coords_elem = None
    for child in ring_elem.iter():
        if _kml_localname(child.tag) == "coordinates":
            coords_elem = child
            break
    if coords_elem is None or not coords_elem.text:
        return []
    points: list[tuple[float, float]] = []
    for tuple_text in coords_elem.text.split():
        parts = tuple_text.split(",")
        if len(parts) < 2:
            continue
        lon, lat = float(parts[0]), float(parts[1])
        points.append((lon, lat))
    return points


def parse_kml_polygons(
    file_bytes: bytes, messages: dict[str, str] | None = None,
) -> Any:
    """Every ``Polygon`` placemark in a KML file, unioned into one geometry.

    Only ``Polygon``/``outerBoundaryIs``/``innerBoundaryIs``/``coordinates``
    elements are read — points, lines, styles and extended data are ignored.
    """
    from defusedxml.ElementTree import fromstring
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    if len(file_bytes) > GEOMETRY_KML_MAX_BYTES:
        raise GeometryError(_tr(
            messages, "err_kml_too_large",
            max_mb=GEOMETRY_KML_MAX_BYTES / (1024 * 1024),
        ))

    try:
        root = fromstring(file_bytes)
    except Exception as exc:  # noqa: BLE001
        raise GeometryError(_tr(messages, "err_kml_parse", exc=exc)) from exc

    polygons: list[Any] = []
    for elem in root.iter():
        if _kml_localname(elem.tag) != "Polygon":
            continue
        shell: list[tuple[float, float]] = []
        holes: list[list[tuple[float, float]]] = []
        for child in elem:
            local = _kml_localname(child.tag)
            if local == "outerBoundaryIs":
                shell = _kml_ring_coords(child)
            elif local == "innerBoundaryIs":
                hole = _kml_ring_coords(child)
                if len(hole) >= 4:
                    holes.append(hole)
        if len(shell) >= 4:
            try:
                polygons.append(Polygon(shell, holes))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping malformed KML polygon: %s", exc)

    if not polygons:
        raise GeometryError(_tr(messages, "err_kml_no_polygon"))

    return polygons[0] if len(polygons) == 1 else unary_union(polygons)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

def _vertex_count(geom: Any) -> int:
    if geom.geom_type == "Polygon":
        return len(geom.exterior.coords) + sum(len(r.coords) for r in geom.interiors)
    if geom.geom_type == "MultiPolygon":
        return sum(_vertex_count(g) for g in geom.geoms)
    return 0


def _area_km2(geom: Any) -> float:
    """True geodesic area — a nominal-projection estimate would be wrong by a
    material amount for a region large enough to matter for the cap below."""
    from pyproj import Geod

    geod = Geod(ellps="WGS84")
    area_m2, _perimeter_m = geod.geometry_area_perimeter(geom)
    return abs(area_m2) / 1_000_000.0


def validate_region(geom: Any, messages: dict[str, str] | None = None) -> Any:
    """Raise :class:`GeometryError` with a user-facing message if unusable;
    otherwise return the (possibly minor-self-intersection-repaired) geometry.

    Mirrors ``geo.validate_for_analysis``: called before any Earth Engine
    work, so a geometry outside MapBiomas' extent or past the cost caps fails
    fast with an explanation rather than as an opaque Earth Engine error.
    """
    from shapely.geometry import box

    if geom is None or geom.is_empty:
        raise GeometryError(_tr(messages, "err_geometry_empty"))

    if not geom.is_valid:
        repaired = geom.buffer(0)
        if repaired.is_empty or not repaired.is_valid:
            raise GeometryError(_tr(messages, "err_geometry_invalid"))
        geom = repaired

    if geom.geom_type not in ("Polygon", "MultiPolygon"):
        raise GeometryError(_tr(messages, "err_geometry_invalid"))

    brazil = box(*BRAZIL_BBOX)
    if not geom.intersects(brazil):
        raise GeometryError(_tr(messages, "err_geometry_outside_brazil"))

    n = _vertex_count(geom)
    if n > GEOMETRY_MAX_VERTICES:
        raise GeometryError(_tr(
            messages, "err_geometry_too_complex", n=n, max_n=GEOMETRY_MAX_VERTICES,
        ))

    area_km2 = _area_km2(geom)
    if area_km2 > GEOMETRY_MAX_AREA_KM2:
        raise GeometryError(_tr(
            messages, "err_geometry_too_large",
            area_km2=area_km2, max_km2=GEOMETRY_MAX_AREA_KM2,
        ))

    return geom


def area_ha(geom: Any) -> float:
    """Public helper for the UI label/badge — same geodesic basis as the cap
    check above, just in hectares instead of km²."""
    return _area_km2(geom) * 100.0


# --------------------------------------------------------------------------- #
# Earth Engine / GeoJSON conversion
# --------------------------------------------------------------------------- #

def region_collection(geom: Any, label: str) -> Any:
    """One feature, in the same shape ``buffers.full_area_collection`` builds
    for a bounding box — ``radius_km``/``shape`` are join keys the shared
    ``_..._from_collection`` reducers read back, not real measurements."""
    import ee
    from shapely.geometry import mapping

    return ee.FeatureCollection([
        ee.Feature(ee.Geometry(mapping(geom)), {
            "radius_km": GEOMETRY_REGION_RADIUS_KM,
            "shape": "polygon",
            "region": True,
            "label": label,
        }),
    ])


def region_geojson(geom: Any, label: str) -> dict[str, Any]:
    """The same region as plain GeoJSON, for the map overlay — drawn with the
    ``drawn_region`` role in leaflet_map.js's overlay effect."""
    from shapely.geometry import mapping

    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": mapping(geom),
            "properties": {"role": "drawn_region", "label": label},
        }],
    }
