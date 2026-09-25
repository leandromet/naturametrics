"""Map views, Earth Engine thumbnails and frame arithmetic — doc/14 §2.6.

A report map is a ``MapComposition``: raster layers fetched from Earth Engine
for one ``MapView`` plus vector layers (outlines, rings, points) drawn by the
renderer. Outlines are never painted in EE: they stay sharp at any zoom, no
geometry is sent over the wire, and the thumbnail cache works per bounding box.

``fetch_thumbnail`` is the kit's ONLY network call. The caller must have
initialised Earth Engine and must run it in an executor (never on the event
loop); in Yvynation's batch it runs before entering a render lane.
"""

from __future__ import annotations

import math
import threading
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from . import style

R_EARTH = 6378137.0
MAX_MERC_LAT = 85.05112878

# --------------------------------------------------------------------------- #
# Geometry helpers (GeoJSON, lon/lat)
# --------------------------------------------------------------------------- #


def iter_coords(geojson: Any) -> Iterator[Tuple[float, float]]:
    """Every (lon, lat) in a GeoJSON Feature/FeatureCollection/Geometry."""
    if not geojson:
        return
    kind = geojson.get("type")
    if kind == "FeatureCollection":
        for feat in geojson.get("features", []):
            yield from iter_coords(feat)
    elif kind == "Feature":
        yield from iter_coords(geojson.get("geometry"))
    elif kind == "GeometryCollection":
        for geom in geojson.get("geometries", []):
            yield from iter_coords(geom)
    else:
        def walk(c):
            if c and isinstance(c[0], (int, float)):
                yield float(c[0]), float(c[1])
            else:
                for sub in c or []:
                    yield from walk(sub)
        yield from walk(geojson.get("coordinates") or [])


def iter_rings(geojson: Any) -> Iterator[Tuple[str, List[List[Tuple[float, float]]]]]:
    """(kind, parts) per primitive: kind is "polygon" (parts = rings),
    "line" (parts = one line) or "point" (parts = one single-point list)."""
    if not geojson:
        return
    kind = geojson.get("type")
    if kind == "FeatureCollection":
        for feat in geojson.get("features", []):
            yield from iter_rings(feat)
        return
    if kind == "Feature":
        yield from iter_rings(geojson.get("geometry"))
        return
    if kind == "GeometryCollection":
        for geom in geojson.get("geometries", []):
            yield from iter_rings(geom)
        return
    coords = geojson.get("coordinates") or []
    as_pts = lambda seq: [(float(p[0]), float(p[1])) for p in seq]  # noqa: E731
    if kind == "Polygon":
        yield "polygon", [as_pts(r) for r in coords]
    elif kind == "MultiPolygon":
        for poly in coords:
            yield "polygon", [as_pts(r) for r in poly]
    elif kind == "LineString":
        yield "line", [as_pts(coords)]
    elif kind == "MultiLineString":
        for line in coords:
            yield "line", [as_pts(line)]
    elif kind == "Point":
        yield "point", [as_pts([coords])]
    elif kind == "MultiPoint":
        for p in coords:
            yield "point", [as_pts([p])]


def bbox_of(geojsons: Iterable[Any]) -> Tuple[float, float, float, float]:
    xs: List[float] = []
    ys: List[float] = []
    for g in geojsons:
        for lon, lat in iter_coords(g):
            xs.append(lon)
            ys.append(lat)
    if not xs:
        raise ValueError("no coordinates to frame")
    return min(xs), min(ys), max(xs), max(ys)


def to_merc(lon: float, lat: float) -> Tuple[float, float]:
    lat = max(-MAX_MERC_LAT, min(MAX_MERC_LAT, lat))
    x = R_EARTH * math.radians(lon)
    y = R_EARTH * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def from_merc(x: float, y: float) -> Tuple[float, float]:
    lon = math.degrees(x / R_EARTH)
    lat = math.degrees(2 * math.atan(math.exp(y / R_EARTH)) - math.pi / 2)
    return lon, lat


# --------------------------------------------------------------------------- #
# The view
# --------------------------------------------------------------------------- #


@dataclass
class MapView:
    """A Web-Mercator window sized for a slot. ``x0..y1`` are EPSG:3857
    metres; ``px_w × px_h`` is the raster size at 150 dpi for the slot."""

    x0: float
    y0: float
    x1: float
    y1: float
    px_w: int
    px_h: int

    @classmethod
    def from_geojson(cls, geojsons: Sequence[Any], slot: str = "full",
                     aspect: float = style.MAP_ASPECT, margin: float = 0.08,
                     min_span_m: float = 1500.0) -> "MapView":
        """Frame ``geojsons`` with ``margin`` on every side, stretched to the
        slot's aspect (height/width) so the fetched raster fills the frame
        exactly. ``min_span_m`` keeps a single point from producing a
        zero-size view."""
        w, s, e, n = bbox_of(geojsons)
        x0, y0 = to_merc(w, s)
        x1, y1 = to_merc(e, n)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        # min_span is ground metres; convert to projected metres at this latitude
        k = 1.0 / max(0.05, math.cos(math.radians((s + n) / 2)))
        span_x = max((x1 - x0) * (1 + 2 * margin), min_span_m * k)
        span_y = max((y1 - y0) * (1 + 2 * margin), min_span_m * k * aspect)
        if span_y / span_x > aspect:
            span_x = span_y / aspect
        else:
            span_y = span_x * aspect
        px_w = style.mm_to_px(style.SLOT_MM[slot])
        px_h = max(1, int(round(px_w * aspect)))
        return cls(cx - span_x / 2, cy - span_y / 2, cx + span_x / 2,
                   cy + span_y / 2, px_w, px_h)

    @property
    def aspect(self) -> float:
        return (self.y1 - self.y0) / (self.x1 - self.x0)

    @property
    def bbox_lonlat(self) -> Tuple[float, float, float, float]:
        w, s = from_merc(self.x0, self.y0)
        e, n = from_merc(self.x1, self.y1)
        return w, s, e, n

    @property
    def centre_lat(self) -> float:
        return from_merc(0.0, (self.y0 + self.y1) / 2)[1]

    @property
    def ground_width_m(self) -> float:
        """True ground width at the centre latitude (Mercator stretches by
        1/cos(lat))."""
        return (self.x1 - self.x0) * math.cos(math.radians(self.centre_lat))

    @property
    def longest_side_km(self) -> float:
        return self.ground_width_m * max(1.0, self.aspect) / 1000.0

    def to_frac(self, lon: float, lat: float) -> Tuple[float, float]:
        """(fx, fy) in the view, 0..1 left→right and TOP→bottom."""
        x, y = to_merc(lon, lat)
        return (x - self.x0) / (self.x1 - self.x0), (self.y1 - y) / (self.y1 - self.y0)


def scale_bar(view: MapView, target_frac: float = 0.2) -> Tuple[float, str]:
    """A round scale-bar length near ``target_frac`` of the map width:
    (fraction of map width, label). 1-2-5 steps; km above 1 km."""
    target_m = view.ground_width_m * target_frac
    exp = 10 ** math.floor(math.log10(max(target_m, 1e-9)))
    best = exp
    for step in (1, 2, 5, 10):
        if step * exp <= target_m:
            best = step * exp
    frac = best / view.ground_width_m
    label = f"{best / 1000:g} km" if best >= 1000 else f"{best:g} m"
    return frac, label


# --------------------------------------------------------------------------- #
# Earth Engine
# --------------------------------------------------------------------------- #

_CACHE: Dict[tuple, bytes] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_MAX = 128


def fetch_thumbnail(image: Any, view: MapView, fmt: str = "png", *,
                    cache_key: str = "", timeout: float = 60.0) -> bytes:
    """Rasterise an already-visualised ``ee.Image`` over ``view``.

    ``fmt`` is "png" (class layers, keeps transparency) or "jpg" (imagery).
    Returns the encoded bytes exactly ``view.px_w × view.px_h``. Cached by
    (cache_key, rounded bbox, size, fmt) when ``cache_key`` is given.
    """
    import ee  # lazy: nothing else in the kit needs Earth Engine

    w, s, e, n = view.bbox_lonlat
    key = (cache_key, round(w, 5), round(s, 5), round(e, 5), round(n, 5),
           view.px_w, view.px_h, fmt) if cache_key else None
    if key is not None:
        with _CACHE_LOCK:
            hit = _CACHE.get(key)
        if hit is not None:
            return hit
    url = image.getThumbURL({
        "region": ee.Geometry.Rectangle([w, s, e, n], None, False),
        "dimensions": f"{view.px_w}x{view.px_h}",
        "crs": "EPSG:3857",
        "format": fmt,
    })
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (EE URL)
        data = resp.read()
    if key is not None:
        with _CACHE_LOCK:
            if len(_CACHE) >= _CACHE_MAX:
                _CACHE.pop(next(iter(_CACHE)))
            _CACHE[key] = data
    return data


S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
S2_CLOUD_SCORE = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
S2_CS_THRESHOLD = 0.60
LANDSAT_ANNUAL = "LANDSAT/COMPOSITES/C02/T1_L2_ANNUAL"
S2_MAX_KM = 50.0
IMAGERY_MAX_KM = 300.0


def imagery_backdrop(view: MapView, year: int) -> Optional[Tuple[Any, str]]:
    """(visualised ``ee.Image``, attribution) for the view's extent, or None.

    ≤ 50 km: Sentinel-2 SR, Cloud Score+ ≥ 0.60, median of the dry season
    (Jun–Sep) of ``year``, falling back to the whole year when the season has
    too few scenes. 50–300 km: the precomputed Landsat annual composite.
    Wider: no imagery — class layers and the locator only.
    """
    import ee

    km = view.longest_side_km
    if km > IMAGERY_MAX_KM:
        return None
    w, s, e, n = view.bbox_lonlat
    region = ee.Geometry.Rectangle([w, s, e, n], None, False)
    if km <= S2_MAX_KM:
        cs = ee.ImageCollection(S2_CLOUD_SCORE)

        def masked(start: str, end: str):
            col = (ee.ImageCollection(S2_COLLECTION).filterBounds(region)
                   .filterDate(start, end).linkCollection(cs, ["cs"]))
            return col.map(lambda img: img.updateMask(
                img.select("cs").gte(S2_CS_THRESHOLD)))

        dry = masked(f"{year}-06-01", f"{year}-10-01")
        full = masked(f"{year}-01-01", f"{year + 1}-01-01")
        col = ee.ImageCollection(ee.Algorithms.If(dry.size().gte(3), dry, full))
        img = col.median().visualize(bands=["B4", "B3", "B2"], min=0, max=3000)
        return img, f"Contains modified Copernicus Sentinel data {year}"
    img = ee.Image(ee.ImageCollection(LANDSAT_ANNUAL)
                   .filterDate(f"{year}-01-01", f"{year}-12-31").first())
    img = img.visualize(bands=["red", "green", "blue"], min=0, max=0.3, gamma=1.2)
    return img, f"Landsat {year}: USGS/NASA (Collection 2 annual composite)"
