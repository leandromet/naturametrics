"""Coordinate handling — one place, one convention, checked at every boundary.

**Why this module exists.** Three coordinate orders meet in this application and
two of them are the reverse of each other:

===================  ==============  ====================================
Consumer             Order           Example (Machadinho d'Oeste, RO)
===================  ==============  ====================================
Leaflet              ``[lat, lon]``  ``[-9.85, -62.95]``
GeoJSON              ``[lon, lat]``  ``[-62.95, -9.85]``
Earth Engine         ``[lon, lat]``  ``ee.Geometry.Point([-62.95, -9.85])``
IFN catalogue CSV    named columns   ``lat=-9.85, lon=-62.95``
===================  ==============  ====================================

A silent swap does not crash. It produces a plausible-looking map somewhere else
on Earth — for Brazilian coordinates, usually the South Atlantic — and every
downstream number is computed over open ocean. This has bitten this project's
sibling apps before.

:func:`validate_for_analysis`'s user-facing message is looked up from the
caller's ``AppState.tr`` (see ``messages`` below) so it renders in whichever
language the UI is in. The invariant checks in ``Point.__post_init__`` stay
Portuguese-only — they guard a programmer error (arguments passed in the
wrong order), not a state reachable through the UI, so no caller has a
language to hand them.

**The rules, enforced below:**

1. Python code passes latitude and longitude as **named arguments**, never as a
   bare pair. ``point(lat=..., lon=...)`` cannot be got wrong; ``point(p)`` can.
2. Conversion to a positional order happens **only** in this module, in a
   function whose name says which order it produces.
3. Every coordinate entering the analysis path is validated against Brazil's
   bounding box. MapBiomas has no data outside it, so a coordinate outside is
   either a user clicking the ocean or a swap — both need to be caught, and the
   distinction is reported.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ..config.settings import BRAZIL_BBOX

logger = logging.getLogger(__name__)

MIN_LON, MIN_LAT, MAX_LON, MAX_LAT = BRAZIL_BBOX


class CoordinateError(ValueError):
    """A coordinate that cannot be used for analysis, with a reason for the user."""


@dataclass(frozen=True)
class Point:
    """A study location. Immutable, and it knows which number is which."""

    lat: float
    lon: float

    def __post_init__(self) -> None:
        if not (-90.0 <= self.lat <= 90.0):
            raise CoordinateError(
                f"Latitude {self.lat} fora de [-90, 90] — os argumentos estão "
                f"quase certamente trocados."
            )
        if not (-180.0 <= self.lon <= 180.0):
            raise CoordinateError(f"Longitude {self.lon} fora de [-180, 180].")

    # --- explicit, named conversions ------------------------------------- #

    def to_leaflet(self) -> list[float]:
        """``[lat, lon]`` — Leaflet's order."""
        return [self.lat, self.lon]

    def to_geojson_coords(self) -> list[float]:
        """``[lon, lat]`` — GeoJSON's order (RFC 7946)."""
        return [self.lon, self.lat]

    def to_geojson(self) -> dict[str, Any]:
        return {"type": "Point", "coordinates": self.to_geojson_coords()}

    def to_ee_point(self):
        """An ``ee.Geometry.Point``. Earth Engine takes ``[lon, lat]``."""
        import ee

        return ee.Geometry.Point(self.to_geojson_coords())

    # --- identity --------------------------------------------------------- #

    def key(self, precision: int = 5) -> str:
        """Stable cache/id key. 5 dp is ~1 m."""
        return f"{self.lat:.{precision}f},{self.lon:.{precision}f}"

    def __str__(self) -> str:
        ns = "S" if self.lat < 0 else "N"
        ew = "W" if self.lon < 0 else "E"
        return f"{abs(self.lat):.5f}°{ns} {abs(self.lon):.5f}°{ew}"


def point(*, lat: float, lon: float) -> Point:
    """Build a :class:`Point`. Keyword-only — that is the whole point."""
    return Point(lat=float(lat), lon=float(lon))


def in_brazil(p: Point) -> bool:
    return MIN_LON <= p.lon <= MAX_LON and MIN_LAT <= p.lat <= MAX_LAT


def looks_swapped(p: Point) -> bool:
    """True if swapping lat/lon would land inside Brazil but the given order does not.

    This is the signature of the exact bug this module exists to prevent, and it
    lets the UI say "did you mean…" instead of "no data here".
    """
    if in_brazil(p):
        return False
    try:
        flipped = Point(lat=p.lon, lon=p.lat)
    except CoordinateError:
        return False
    return in_brazil(flipped)


#: Fallback wording if a caller does not pass ``messages`` — kept so every
#: existing call site (and any test) that predates i18n keeps working.
_DEFAULT_MESSAGES = {
    "err_coord_swapped": (
        "{point} está fora do Brasil, mas {flipped} está dentro — latitude "
        "e longitude parecem trocadas."
    ),
    "err_coord_outside_brazil": (
        "{point} está fora do Brasil. O MapBiomas cobre apenas o Brasil, "
        "portanto não há histórico de cobertura do solo para este local."
    ),
}


def validate_for_analysis(p: Point, messages: dict[str, str] | None = None) -> None:
    """Raise :class:`CoordinateError` with a user-facing message if unusable.

    Called before any Earth Engine work — reducing over a geometry outside
    MapBiomas' extent wastes a round-trip and returns an empty histogram that
    looks like a bug rather than an out-of-area click.

    ``messages`` carries the two ``err_coord_*`` keys from the caller's
    ``AppState.tr`` — this module stays decoupled from the translations
    package and just formats whatever templates it is handed.
    """
    if in_brazil(p):
        return
    messages = messages or _DEFAULT_MESSAGES
    if looks_swapped(p):
        raise CoordinateError(messages["err_coord_swapped"].format(
            point=str(p), flipped=str(Point(lat=p.lon, lon=p.lat))))
    raise CoordinateError(messages["err_coord_outside_brazil"].format(point=str(p)))
