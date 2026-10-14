"""Resolving what the user typed into the Canada page's location search.

Ported from camposcope's Canada resolver, trimmed: this page has no parcel
fabric and no municipality table, so there is no PID or area resolver. Three
resolvers, tried in a fixed order and stopping at the first match: a postal
code, a coordinate, a place name or street address. The first two are exact
(a postal code is recognised locally, then looked up); only the last is a
guess against third-party services — DataBC's Address Geocoder for a BC civic
address, then Nominatim (see ``naturametrics/services/address.py``).

**A place result frames the map and selects nothing.** Only an exact
coordinate selects a study point — the search box's equivalent of clicking the
map there, same split as the Brazil page's ``state/_search.py``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, List, Optional

from ...config.settings import (
    GEOCODER_ENABLED,
    GEOCODER_TIMEOUT_CONNECT,
    GEOCODER_TIMEOUT_READ,
    GEOCODER_URL,
    GEOCODER_USER_AGENT,
)
from ...services import address
from ...services.address import Place
from ..config.settings import CANADA_BBOX

logger = logging.getLogger(__name__)

CA_WEST, CA_SOUTH, CA_EAST, CA_NORTH = CANADA_BBOX


class GeocodeError(RuntimeError):
    """A failure talking to the geocoding service."""


def _in_canada(lat: float, lon: float) -> bool:
    return CA_SOUTH <= lat <= CA_NORTH and CA_WEST <= lon <= CA_EAST


# --------------------------------------------------------------------------- #
# Coordinates
# --------------------------------------------------------------------------- #
#: A Google Maps URL carries the coordinate in one of two places.
_GMAPS_AT = re.compile(r"@(-?\d+(?:[.,]\d+)?),(-?\d+(?:[.,]\d+)?)")
_GMAPS_Q = re.compile(r"[?&]q=(-?\d+(?:[.,]\d+)?)(?:,|%2C)\s*(-?\d+(?:[.,]\d+)?)")

#: 49°53'16.8"N  /  49 53 16.8 N  /  49º53'16.8''N
_DMS = re.compile(
    r"""(?P<deg>\d{1,3})\s*[°º:\s]\s*
        (?P<min>\d{1,2})\s*['′:\s]\s*
        (?P<sec>\d{1,2}(?:[.,]\d+)?)\s*(?:["”″']{0,2})\s*
        (?P<hem>[NSEWLO])""",
    re.VERBOSE | re.IGNORECASE,
)

_DECIMAL_PAIR = re.compile(
    r"^\s*(-?\d{1,3}(?:[.,]\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:[.,]\d+)?)\s*$"
)


@dataclass(frozen=True)
class Coordinate:
    lat: float
    lon: float
    source: str          # "decimal" | "dms" | "gmaps"


def _to_float(raw: str) -> float:
    """Accept ``.`` or ``,`` as the decimal separator.

    Kept from the Brazil resolver even though the Canada page defaults to
    English: the two pages share a user, and someone who pastes
    ``49,88 -119,49`` out of habit deserves an answer rather than a fall-through
    to an address search.
    """
    return float(raw.strip().replace(",", "."))


def _hemisphere_sign(hem: str) -> int:
    # 'L' = leste and 'O' = oeste, the Portuguese cardinal letters — a
    # pt-BR-keyboard user on the Canada page still types them.
    return -1 if hem.upper() in ("S", "W", "O") else 1


def parse_coordinates(text: str) -> Optional[Coordinate]:
    """Parse a coordinate in any of the formats users actually paste.

    Returns ``None`` when the text is not a coordinate at all — not an error,
    it just means the next resolver should try. Raises ``ValueError`` when the
    text *is* a coordinate but an unusable one, because that deserves a message
    rather than a silent fall-through to a place-name search.

    **Latitude first**, always. The CQL the service layer builds is
    ``POINT(lon lat)``, and that inversion lives there, not here.
    """
    raw = (text or "").strip()
    if not raw:
        return None

    # --- Google Maps URL ---------------------------------------------------
    for pattern in (_GMAPS_AT, _GMAPS_Q):
        m = pattern.search(raw)
        if m:
            return _validated(_to_float(m.group(1)), _to_float(m.group(2)),
                              "gmaps")

    # --- DMS ---------------------------------------------------------------
    dms = list(_DMS.finditer(raw))
    if len(dms) >= 2:
        values: Dict[str, float] = {}
        for m in dms[:2]:
            deg = float(m.group("deg"))
            minutes = float(m.group("min"))
            seconds = _to_float(m.group("sec"))
            hem = m.group("hem").upper()
            decimal = (deg + minutes / 60 + seconds / 3600) * _hemisphere_sign(hem)
            values["lat" if hem in ("N", "S") else "lon"] = decimal
        if "lat" in values and "lon" in values:
            return _validated(values["lat"], values["lon"], "dms")

    # --- decimal pair ------------------------------------------------------
    m = _DECIMAL_PAIR.match(raw)
    if m:
        a, b = m.group(1), m.group(2)
        # "49,88 -119,49" is two comma-decimals separated by a space; but
        # "49.88, -119.49" is two dot-decimals separated by a comma. Both match
        # the same pattern, and only the presence of a dot tells them apart —
        # so a value containing BOTH is ambiguous and refused.
        if "," in a and "." in a:
            raise ValueError(f"Ambiguous coordinate: {a!r}")
        return _validated(_to_float(a), _to_float(b), "decimal")

    return None


def _validated(lat: float, lon: float, source: str) -> Coordinate:
    """Refuse a coordinate outside Canada, naming which value looks wrong.

    Transposition is still worth catching on its own terms: Canada's latitude
    range (41–83.5) and longitude range (-141.5 to -52) do not overlap, so a
    swapped pair is unambiguous rather than merely suspicious, and left
    unchecked it lands somewhere on a different continent with nothing to say
    why.
    """
    # A bounding box, not camposcope's boundary lookup: this page has no BC
    # tier to route to, and set_study_point makes the exact in-Canada check
    # (and says why) once the point arrives.
    if _in_canada(lat, lon):
        return Coordinate(lat=lat, lon=lon, source=source)

    if _in_canada(lon, lat):
        raise ValueError(
            f"That is outside Canada, but {lon:.4f}, {lat:.4f} would be "
            "inside — the values look transposed. Latitude comes first."
        )

    culprit = []
    if not (CA_SOUTH <= lat <= CA_NORTH):
        culprit.append(
            f"latitude {lat:.4f} (expected between {CA_SOUTH} and {CA_NORTH})")
    if not (CA_WEST <= lon <= CA_EAST):
        culprit.append(
            f"longitude {lon:.4f} (expected between {CA_WEST} and {CA_EAST})")
    raise ValueError("Coordinate outside Canada: " + "; ".join(culprit) + ".")


# --------------------------------------------------------------------------- #
# Place names, street addresses and postal codes
# --------------------------------------------------------------------------- #
_geocoder = address.AddressGeocoder(
    url=GEOCODER_URL,
    user_agent=GEOCODER_USER_AGENT,
    accept_language="en-CA,en",
    countrycodes="ca",
    enabled=GEOCODER_ENABLED,
    timeout=(GEOCODER_TIMEOUT_CONNECT, GEOCODER_TIMEOUT_READ),
    # countrycodes=ca still lets through the odd cross-border match (a
    # "Vancouver" in Washington State); the bbox drops it.
    keep=_in_canada,
    viewbox=CANADA_BBOX,
)


def search_places(query: str, *, limit: int = 6) -> List[Place]:
    """Geocode a place name or street address — the last resort.

    A query that starts with a civic number asks BC's address register first;
    an exact civic match there is the answer on its own. Otherwise OSM.
    """
    if not GEOCODER_ENABLED:
        raise GeocodeError("Place search is disabled in this installation.")
    bc = (_geocoder.search_bc_address(query)
          if address.looks_like_street_address(query) else [])
    if any(p.precision == "endereco" for p in bc):
        return bc[:limit]
    try:
        osm = _geocoder.search(query, limit=limit)
    except address.AddressError as exc:
        if bc:
            return bc[:limit]
        raise GeocodeError(f"Could not reach the place-search service: {exc}")
    return address.merge(bc, osm, limit=limit)


def search_postal(code: str) -> List[Place]:
    """A postal code (``V1Y 2B3``) → its centroid."""
    if not GEOCODER_ENABLED:
        raise GeocodeError("Place search is disabled in this installation.")
    try:
        return _geocoder.search_ca_postal(code)
    except address.AddressError as exc:
        raise GeocodeError(f"Could not reach the place-search service: {exc}")


# --------------------------------------------------------------------------- #
# The unified resolver
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Resolution:
    """What the search box decided the input was — drives both the action
    and the echo line shown *before* acting."""

    kind: str        # "postal" | "coordenada" | "lugar" | "vazio"
    echo: str
    payload: Any = None


def resolve(text: str) -> Resolution:
    """Classify the input without performing any network call."""
    raw = (text or "").strip()
    if not raw:
        return Resolution("vazio", "")

    postal = address.parse_ca_postal(raw)
    if postal:
        return Resolution("postal", f"postal code {postal}", postal)

    coord = parse_coordinates(raw)
    if coord is not None:
        return Resolution("coordenada",
                          f"coordinate {coord.lat:.4f}, {coord.lon:.4f}", coord)

    return Resolution("lugar", f"place “{raw}”", raw)


__all__ = [
    "Coordinate", "Place", "Resolution", "GeocodeError",
    "parse_coordinates", "search_places", "search_postal", "resolve",
]
