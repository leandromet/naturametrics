"""USA-page settings (lower 48).

Deliberately thin, like the Canada page's: everything about *Earth Engine* rather
than about the country (project id, concurrency, tile cache, scale, buffer radii,
export budgets, abuse control) comes from :mod:`naturametrics.config.settings`.
"""

from __future__ import annotations

import os

from ...config.settings import _float, _int

#: Boxes (min_lon, min_lat, max_lon, max_lat) of the three regions this page covers. Coarse quick
#: tests only: the conterminous box overlaps Canada and Mexico along the borders and the Alaska one
#: overlaps Yukon/BC, so the country itself is settled by the LSIB boundary dataset
#: (``services/geo.py``). West of 170°W (the outer Aleutians, across the antimeridian) is left out;
#: Puerto Rico and the other territories are not covered.
REGION_BOXES = {
    "conus": (-125.0, 24.4, -66.8, 49.5),
    "ak": (-170.0, 51.0, -129.9, 71.6),
    "hi": (-160.5, 18.8, -154.7, 22.3),
}
#: One box around all of them, for the cheapest possible rejection.
USA_BBOX = (-170.0, 18.8, -66.8, 71.6)

MAP_CENTER: tuple[float, float] = (
    _float("NM_US_MAP_CENTER_LAT", 39.5),
    _float("NM_US_MAP_CENTER_LON", -98.5),
)
MAP_ZOOM = _int("NM_US_MAP_ZOOM", 4)

#: Initial framing as [[south, west], [north, east]].
USA_VIEW_BOUNDS: tuple[tuple[float, float], tuple[float, float]] = (
    (24.4, -125.0),
    (49.5, -66.8),
)

#: Like the Canada page, opens in English; an explicit choice by the user wins.
DEFAULT_LANGUAGE = os.environ.get("NM_US_LANGUAGE", "en")
