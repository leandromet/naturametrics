"""Coordinate validation for the world page.

``Point`` is the Brazil page's, unchanged (it already checks −90…90 and −180…180). The country
pages add a boundary test (a box, then LSIB); the world has none, only the span the data covers:
60°S–85°N. A point over the sea is *valid* — it simply has no land-cover pixels, and the analysis
says so — so there is no Earth Engine call here.
"""

from __future__ import annotations

from ...services.geo import CoordinateError, Point, point  # noqa: F401
from ..config.settings import REGION_BOXES, WORLD_BBOX

MIN_LON, MIN_LAT, MAX_LON, MAX_LAT = WORLD_BBOX

_DEFAULT_MESSAGES = {
    "err_coord_swapped": "{point} is outside the covered world — latitude and longitude look swapped.",
    "err_coord_outside_world": "{point} is outside the span the world page covers (60°S to 85°N).",
}


def region_of(p: Point) -> str | None:
    """``"world"`` inside the analysable span, else None."""
    w, s, e, n = REGION_BOXES["world"]
    return "world" if (w <= p.lon <= e and s <= p.lat <= n) else None


def in_world_box(p: Point) -> bool:
    return region_of(p) is not None


def in_world(p: Point) -> bool:
    return in_world_box(p)


def looks_swapped(p: Point) -> bool:
    """True if swapping lat/lon would land inside the span but the given order does not."""
    if in_world(p):
        return False
    try:
        flipped = Point(lat=p.lon, lon=p.lat)
    except CoordinateError:
        return False
    return in_world_box(flipped)


def validate_for_analysis(p: Point, messages: dict[str, str] | None = None) -> None:
    """Raise :class:`CoordinateError` if the point is outside the analysable span."""
    if in_world(p):
        return
    messages = messages or _DEFAULT_MESSAGES
    if looks_swapped(p):
        raise CoordinateError(messages["err_coord_swapped"].format(
            point=str(p), flipped=str(Point(lat=p.lon, lon=p.lat))))
    raise CoordinateError(messages["err_coord_outside_world"].format(point=str(p)))
