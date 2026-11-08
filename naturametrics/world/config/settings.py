"""World-page settings.

Deliberately thin, like the other country pages': everything about *Earth Engine* rather than
about a place (project id, concurrency, tile cache, scale, buffer radii, export budgets, abuse
control) comes from :mod:`naturametrics.config.settings`.
"""

from __future__ import annotations

import os

from ...config.settings import _float, _int

#: The analysable world: the span of GLC-FCS30D and the world climate blocks (60°S–85°N). The region
#: idea of the country pages (a box per region, settled by LSIB) is one box here, and no LSIB call.
REGION_BOXES = {"world": (-180.0, -60.0, 180.0, 85.0)}
WORLD_BBOX = REGION_BOXES["world"]

#: Opens on Brazil and Africa, with the Atlantic between: a light first load (two GLC tile groups).
MAP_CENTER: tuple[float, float] = (
    _float("NM_WORLD_MAP_CENTER_LAT", -5.0),
    _float("NM_WORLD_MAP_CENTER_LON", -8.0),
)
MAP_ZOOM = _int("NM_WORLD_MAP_ZOOM", 3)

#: Initial framing as [[south, west], [north, east]].
WORLD_VIEW_BOUNDS: tuple[tuple[float, float], tuple[float, float]] = (
    (-34.0, -75.0),
    (20.0, 50.0),
)

#: Like the Canada and USA pages, opens in English; an explicit choice by the user wins.
DEFAULT_LANGUAGE = os.environ.get("NM_WORLD_LANGUAGE", "en")
