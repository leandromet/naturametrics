"""Resolving what the user typed into the location search box.

Ported from camposcope's module of the same name, trimmed: naturametrics has
no property registry, so there is no CAR-code resolver here. Three resolvers,
tried in a fixed order and stopping at the first match: a coordinate, a
município, a place name. The first two are exact and local; only the third
reaches a third-party service (Nominatim), which is what keeps geocoder usage
defensible — most searches never reach it at all.

**A place-name result frames the map and selects nothing; a município result
does too.** Only an exact coordinate selects a study point (the search box's
equivalent of clicking the map there) — see state/_search.py.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from ..config.settings import (
    BRAZIL_BBOX,
    GEOCODER_COUNTRY_CODES,
    GEOCODER_ENABLED,
    GEOCODER_TIMEOUT_CONNECT,
    GEOCODER_TIMEOUT_READ,
    GEOCODER_URL,
    GEOCODER_USER_AGENT,
)

logger = logging.getLogger(__name__)

WEST, SOUTH, EAST, NORTH = BRAZIL_BBOX


class GeocodeError(RuntimeError):
    """A failure talking to the geocoding service."""


# --------------------------------------------------------------------------- #
# Coordinates
# --------------------------------------------------------------------------- #
#: A Google Maps URL carries the coordinate in one of two places.
_GMAPS_AT = re.compile(r"@(-?\d+(?:[.,]\d+)?),(-?\d+(?:[.,]\d+)?)")
_GMAPS_Q = re.compile(r"[?&]q=(-?\d+(?:[.,]\d+)?)(?:,|%2C)\s*(-?\d+(?:[.,]\d+)?)")

#: 12°29'52.5"S  /  12 29 52.5 S  /  12º29'52.5''S
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

    pt-BR keyboards produce commas, and ``-12,4979 -55,4977`` is a real thing
    users paste.
    """
    return float(raw.strip().replace(",", "."))


def _hemisphere_sign(hem: str) -> int:
    # 'L' = leste and 'O' = oeste, the Portuguese cardinal letters.
    return -1 if hem.upper() in ("S", "W", "O") else 1


def _in_brazil(lat: float, lon: float) -> bool:
    return SOUTH <= lat <= NORTH and WEST <= lon <= EAST


def parse_coordinates(text: str) -> Optional[Coordinate]:
    """Parse a coordinate in any of the formats users actually paste.

    Returns ``None`` when the text is not a coordinate at all — that is not an
    error, it just means the next resolver should try. Raises ``ValueError``
    when the text *is* a coordinate but an unusable one, because that deserves a
    message rather than a silent fall-through to a place-name search.

    **Latitude first**, always.
    """
    raw = (text or "").strip()
    if not raw:
        return None

    # --- Google Maps URL ---------------------------------------------------
    for pattern in (_GMAPS_AT, _GMAPS_Q):
        m = pattern.search(raw)
        if m:
            lat, lon = _to_float(m.group(1)), _to_float(m.group(2))
            return _validated(lat, lon, "gmaps")

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
        # "-12,4979 -55,4977" is two comma-decimals separated by a space; but
        # "-12.4979, -55.4977" is two dot-decimals separated by a comma. Both
        # match the same pattern, and only the presence of a dot tells them
        # apart — so a value containing BOTH is ambiguous and refused.
        if "," in a and "." in a:
            raise ValueError(f"Coordenada ambígua: {a!r}")
        return _validated(_to_float(a), _to_float(b), "decimal")

    return None


def _validated(lat: float, lon: float, source: str) -> Coordinate:
    """Refuse a coordinate outside Brazil, naming which value looks wrong.

    A transposed pair (``-55.5, -12.5``) lands in the South Atlantic, and
    "nada encontrado neste ponto" would be a terrible answer to a transposition.
    """
    if _in_brazil(lat, lon):
        return Coordinate(lat=lat, lon=lon, source=source)

    if _in_brazil(lon, lat):
        raise ValueError(
            f"Coordenada fora do Brasil, mas {lon:.4f}, {lat:.4f} estaria dentro "
            "— os valores parecem invertidos. A latitude vem primeiro."
        )
    culprit = []
    if not (SOUTH <= lat <= NORTH):
        culprit.append(f"latitude {lat:.4f} (esperado entre {SOUTH} e {NORTH})")
    if not (WEST <= lon <= EAST):
        culprit.append(f"longitude {lon:.4f} (esperado entre {WEST} e {EAST})")
    raise ValueError("Coordenada fora do Brasil: " + "; ".join(culprit) + ".")


# --------------------------------------------------------------------------- #
# Place names
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Place:
    """A geocoded place. Frames the map; never selects a point."""

    label: str
    lat: float
    lon: float
    #: ``[[south, west], [north, east]]`` — framing a bbox is honest about
    #: uncertainty in a way a single pin is not.
    bounds: Optional[List[List[float]]]
    attribution: str = "© colaboradores do OpenStreetMap (ODbL)"


#: Nominatim's policy caps us at ~1 request/second and forbids bulk use, so
#: requests serialise through here.
_LOCK = threading.Lock()
_cache: Dict[str, List[Place]] = {}
_cache_lock = threading.Lock()
_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({
            "User-Agent": GEOCODER_USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "pt-BR,pt",
        })
        _session = s
    return _session


def search_places(query: str, *, limit: int = 5) -> List[Place]:
    """Geocode a place name. **The last resort, never the first try.**

    Callers must have already ruled out a coordinate and a município — see
    :func:`resolve`. Results are cached for the process lifetime; a place name
    does not move.
    """
    q = (query or "").strip()
    if not q:
        return []
    if not GEOCODER_ENABLED:
        raise GeocodeError("A busca por lugares está desativada nesta instalação.")

    key = f"{q.lower()}:{limit}"
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None:
            return hit

    params = {
        "q": q,
        "format": "jsonv2",
        "limit": limit,
        # Never widen this. The app covers Brazil; a search that can wander off
        # it will.
        "countrycodes": GEOCODER_COUNTRY_CODES,
    }

    with _LOCK:
        try:
            r = _get_session().get(
                GEOCODER_URL,
                params=params,
                timeout=(GEOCODER_TIMEOUT_CONNECT, GEOCODER_TIMEOUT_READ),
            )
        except requests.RequestException as exc:
            raise GeocodeError(f"Não foi possível contatar o serviço de busca: {exc}")
        # One request per second is the policy; hold the lock for it rather than
        # trusting callers to pace themselves.
        time.sleep(1.0)

    if r.status_code != 200:
        raise GeocodeError(f"O serviço de busca respondeu HTTP {r.status_code}.")

    try:
        payload = r.json()
    except ValueError as exc:
        raise GeocodeError("Resposta inesperada do serviço de busca.") from exc

    places: List[Place] = []
    for item in payload:
        try:
            lat, lon = float(item["lat"]), float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        bbox = item.get("boundingbox")
        bounds = None
        if bbox and len(bbox) == 4:
            try:
                s, n, w, e = (float(v) for v in bbox)
                bounds = [[s, w], [n, e]]
            except (TypeError, ValueError):
                bounds = None
        places.append(Place(
            label=item.get("display_name", q),
            lat=lat, lon=lon, bounds=bounds,
        ))

    with _cache_lock:
        _cache[key] = places
    return places


# --------------------------------------------------------------------------- #
# The unified resolver
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Resolution:
    """What the search box decided the input was.

    ``kind`` drives both the action and the echo line the UI shows *before*
    acting — the line that stops a transposed coordinate pair from quietly
    resolving somewhere plausible and wrong.
    """

    kind: str            # "coordenada" | "municipio" | "lugar" | "vazio"
    echo: str            # human-readable "read as …"
    payload: Any = None


def resolve(text: str) -> Resolution:
    """Classify the input without performing any network call.

    Deliberately does **not** geocode: it says *what it would do*, and the
    caller performs it. That keeps the echo line honest — the UI can show how
    the input was read before a single request goes out.
    """
    raw = (text or "").strip()
    if not raw:
        return Resolution("vazio", "")

    # 1 — coordinate. Exact and local. A ValueError here is a real message.
    coord = parse_coordinates(raw)
    if coord is not None:
        return Resolution(
            "coordenada",
            f"coordenada {coord.lat:.4f}, {coord.lon:.4f}",
            coord,
        )

    # 2 — município. Exact and local.
    from . import municipios

    matches = municipios.search(raw, limit=5)
    if matches:
        first = matches[0]
        return Resolution(
            "municipio",
            f"município {first['nome']}/{first['uf']}",
            matches,
        )

    # 3 — place name. The only resolver that touches a third party.
    return Resolution("lugar", f"lugar “{raw}”", raw)


__all__ = [
    "Coordinate", "Place", "Resolution", "GeocodeError",
    "parse_coordinates", "search_places", "resolve",
]
