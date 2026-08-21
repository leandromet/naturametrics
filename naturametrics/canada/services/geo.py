"""Canadian coordinate validation.

``Point`` itself is imported unchanged from the Brazil page's
:mod:`naturametrics.services.geo` — the lat/lon ordering discipline that module
exists to enforce is not country-specific, and duplicating it would be exactly
the kind of second copy it warns about. Only the *extent* questions are
Canadian, and they live here.

**Two different answers, on purpose.** Brazil has one bound: outside MapBiomas'
extent there is no data of any kind, so a click there is refused. Canada has two
nested bounds, because its datasets have different footprints:

* Outside **Canada** — refused, same as Brazil. Nothing here answers.
* Inside Canada but north of the **AAFC ACI** extent (~54–58°N, ragged) — the
  click is **allowed**. NTEMS forest age and Hansen GFC are national/global and
  answer normally; only the land-cover history has nothing to show, and it says
  so in its own panel rather than blocking the whole analysis.

That second case is most of Canada's landmass, which is why it cannot be an
error. See ``config/aafc.py`` for the sampled coverage evidence.
"""

from __future__ import annotations

import logging

from ...services.geo import CoordinateError, Point, point  # noqa: F401
from ..config.aafc import ACI_NORTH_LIMIT_LAT
from ..config.settings import CANADA_BBOX

logger = logging.getLogger(__name__)

MIN_LON, MIN_LAT, MAX_LON, MAX_LAT = CANADA_BBOX

#: Fallback wording when a caller passes no ``messages`` — mirrors the pattern in
#: the Brazil geo module so tests and non-UI callers keep working.
_DEFAULT_MESSAGES = {
    "err_coord_swapped": (
        "{point} is outside Canada, but {flipped} is inside — latitude and "
        "longitude look swapped."
    ),
    "err_coord_outside_canada": (
        "{point} is outside Canada. This page covers Canada only; use the "
        "Brazil page for South American coordinates."
    ),
}


def in_canada(p: Point) -> bool:
    return MIN_LON <= p.lon <= MAX_LON and MIN_LAT <= p.lat <= MAX_LAT


def looks_swapped(p: Point) -> bool:
    """True if swapping lat/lon would land inside Canada but the given order does not."""
    if in_canada(p):
        return False
    try:
        flipped = Point(lat=p.lon, lon=p.lat)
    except CoordinateError:
        return False
    return in_canada(flipped)


def north_of_aci(p: Point) -> bool:
    """Whether the Annual Crop Inventory is expected to have nothing here.

    A latitude test, not a lookup against the real (ragged) footprint: the
    authoritative answer is simply whether the reducer returns an empty
    histogram, which the analysis already handles. This exists only so the UI
    can say *why* a panel is empty before the query returns, and so it errs
    toward the honest "may have no data" rather than a false promise.
    """
    return p.lat > ACI_NORTH_LIMIT_LAT


def validate_for_analysis(p: Point, messages: dict[str, str] | None = None) -> None:
    """Raise :class:`CoordinateError` if the point is not in Canada at all.

    Note what this does *not* do: it never refuses a point for being north of
    the ACI extent. See the module docstring.
    """
    if in_canada(p):
        return
    messages = messages or _DEFAULT_MESSAGES
    if looks_swapped(p):
        raise CoordinateError(messages["err_coord_swapped"].format(
            point=str(p), flipped=str(Point(lat=p.lon, lon=p.lat))))
    raise CoordinateError(
        messages["err_coord_outside_canada"].format(point=str(p)))
