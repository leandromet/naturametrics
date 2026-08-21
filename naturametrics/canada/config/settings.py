"""Canada-page settings.

Deliberately thin: everything that is about *Earth Engine* rather than about
Canada (project id, concurrency, tile cache, scale, buffer radii, export budgets,
abuse control) is imported from the main :mod:`naturametrics.config.settings`,
because those are properties of the deployment and must not drift between the
two pages. Only what is genuinely Canadian lives here.
"""

from __future__ import annotations

import os

from ...config.settings import _float, _int

# --------------------------------------------------------------------------- #
# Extent
# --------------------------------------------------------------------------- #
#: Generous bbox around Canada — used to reject clicks that are not in the
#: country at all. min_lon, min_lat, max_lon, max_lat.
#: Canada spans lon -141..-52.6, lat 41.7..83.1; padded so the outline is not
#: flush against the edge.
CANADA_BBOX = (-141.5, 41.0, -52.0, 83.5)

# --------------------------------------------------------------------------- #
# Map defaults
# --------------------------------------------------------------------------- #
#: Centred low rather than on the geographic centre. Canada's centroid sits in
#: Nunavut, which would put the populated south — and the entire ACI extent —
#: in the bottom sliver of the map pane.
MAP_CENTER: tuple[float, float] = (
    _float("NM_CA_MAP_CENTER_LAT", 56.0),
    _float("NM_CA_MAP_CENTER_LON", -96.0),
)
MAP_ZOOM = _int("NM_CA_MAP_ZOOM", 4)

#: Initial framing as [[south, west], [north, east]]. Stops at 72°N rather than
#: 83.5: including the Arctic islands triples the vertical span for a strip
#: almost nobody clicks, and shrinks the settled south to nothing.
CANADA_VIEW_BOUNDS: tuple[tuple[float, float], tuple[float, float]] = (
    (41.0, -141.5),
    (72.0, -52.0),
)

# --------------------------------------------------------------------------- #
# Language
# --------------------------------------------------------------------------- #
#: The Canada page opens in English; the Brazil page opens in Portuguese. The
#: switcher is shared, and an explicit choice by the user wins over both — see
#: ``canada/state/_ui.py``.
DEFAULT_LANGUAGE = os.environ.get("NM_CA_LANGUAGE", "en")
