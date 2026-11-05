"""US coordinate validation (lower 48, Alaska, Hawaii).

``Point`` is the Brazil page's, unchanged. Two bounds, cheapest first:

1. A bounding box of the conterminous US (``USA_BBOX``). It rejects most clicks
   for free, but it also contains southern Canada (Toronto, Vancouver) and
   northern Mexico, so a box alone is not enough.
2. The **LSIB** boundary dataset (``USDOS/LSIB/2017``) settles a point inside the
   box. Cached by 0.01° cell (~1 km) so a session pays for one lookup per place.
   The "SIMPLE" LSIB returned nothing at test points; the full one is used.

Covered: the lower 48, Alaska (east of 170°W) and Hawaii. Annual NLCD is conterminous-only, so
Alaska and Hawaii get its three snapshot years (2001, 2011, 2016); LCMS, MTBS, Tree Canopy Cover and
Hansen cover all three. Puerto Rico and the other territories are not covered.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from ...services.ee_client import get_ee
from ...services.geo import CoordinateError, Point, point  # noqa: F401
from ..config.settings import REGION_BOXES, USA_BBOX

logger = logging.getLogger(__name__)

MIN_LON, MIN_LAT, MAX_LON, MAX_LAT = USA_BBOX

_DEFAULT_MESSAGES = {
    "err_coord_swapped": (
        "{point} is outside the covered United States, but {flipped} is inside — latitude and "
        "longitude look swapped."
    ),
    "err_coord_outside_usa": (
        "{point} is outside the covered United States (lower 48, Alaska and Hawaii). Use "
        "the Brazil or Canada page for other coordinates."
    ),
}


def region_of(p: Point) -> str | None:
    """``"conus"`` | ``"ak"`` | ``"hi"`` by bounding box (the country itself is LSIB's call)."""
    for code, (w, s, e, n) in REGION_BOXES.items():
        if w <= p.lon <= e and s <= p.lat <= n:
            return code
    return None


def in_usa_box(p: Point) -> bool:
    return region_of(p) is not None


@lru_cache(maxsize=4096)
def _is_us_cell(lat_c: int, lon_c: int) -> bool:
    """LSIB lookup for one 0.01° cell, given as integer hundredths of a degree."""
    ee = get_ee()
    pt = ee.Geometry.Point([lon_c / 100.0, lat_c / 100.0])
    names = (ee.FeatureCollection("USDOS/LSIB/2017").filterBounds(pt)
             .aggregate_array("COUNTRY_NA").getInfo())
    return "United States" in names


def in_usa(p: Point) -> bool:
    """Inside the lower 48: box first, then LSIB. LSIB failing never blocks a click
    that is plainly inside the box's interior; at the edges it errs toward refusing."""
    if not in_usa_box(p):
        return False
    try:
        return _is_us_cell(round(p.lat * 100), round(p.lon * 100))
    except Exception:  # EE unavailable: fall back to the box rather than block the page
        logger.warning("LSIB lookup failed for %s; falling back to the bounding box", p)
        return True


def looks_swapped(p: Point) -> bool:
    """True if swapping lat/lon would land inside the US but the given order does not."""
    if in_usa(p):
        return False
    try:
        flipped = Point(lat=p.lon, lon=p.lat)
    except CoordinateError:
        return False
    return in_usa_box(flipped) and in_usa(flipped)


def validate_for_analysis(p: Point, messages: dict[str, str] | None = None) -> None:
    """Raise :class:`CoordinateError` if the point is not in the lower 48."""
    if in_usa(p):
        return
    messages = messages or _DEFAULT_MESSAGES
    if looks_swapped(p):
        raise CoordinateError(messages["err_coord_swapped"].format(
            point=str(p), flipped=str(Point(lat=p.lon, lon=p.lat))))
    raise CoordinateError(messages["err_coord_outside_usa"].format(point=str(p)))
