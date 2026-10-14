"""Address-grade geocoding behind every search box's last resolver.

The resolvers in ``geocode.py`` decide *what* the input is; this module only
answers the one question they cannot answer locally — "where is this
address / postal code / place?" — and answers it better than a bare
free-text Nominatim call did:

* **Postal codes are their own resolver.** A Brazilian CEP (``78890-000``) or a
  Canadian postal code (``V1Y 2B3``) is unambiguous, and Nominatim has both
  in its postcode table — but only when asked with ``postalcode=``, not as
  free text. For a CEP, ViaCEP adds the street / bairro / município the code
  belongs to, so the result reads as an address instead of a bare number.
* **Results carry a precision.** ``endereco`` (a house number), ``rua``,
  ``cep``, ``bairro``, ``cidade``, ``regiao`` or ``lugar`` — the UI uses it to
  decide between a tight zoom with a pin and a framed bounding box, and shows
  it so a street-level hit is not mistaken for a town-level one.
* **Labels are two lines.** Nominatim's ``display_name`` is a ten-part comma
  list; ``addressdetails=1`` lets the title be "Avenida Paulista, 1000" and the
  subtitle "Bela Vista, São Paulo – SP".
* **British Columbia civic addresses** go to DataBC's Address Geocoder first —
  the province's authoritative address register, keyless, and far better than
  OSM on rural roads, where most of the parcels this suite cares about are.

Every service here is public and keyless. Nominatim's usage policy caps us at
one request per second and forbids bulk use, so its calls serialise through a
process-wide lock that holds for that second; results are cached for the
process lifetime (an address does not move).

**A geocoded result frames the map and selects nothing.** That rule lives in
the state layer, but it is the reason ``Place`` carries a precision and a
bounding box rather than pretending to be an exact point.

Shared by the three apps and checked by hash: the canonical copy is
``/server/naturametrics/naturametrics/services/address.py``. Edit it there, then run
``python scripts/sync_shared_files.py`` in Naturametrics, which copies it to
Camposcope and Yvynation and rewrites each app's ``tests/shared_files.sha256``.
An edit made in any other copy fails that app's ``tests/test_shared_files.py``.
"""

from __future__ import annotations

import logging
import re
import threading
import time
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

OSM_ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"
VIACEP_ATTRIBUTION = "CEP: ViaCEP"
BC_ATTRIBUTION = ("Contains information licensed under the Open Government "
                  "Licence – British Columbia")

VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"
BC_GEOCODER_URL = "https://geocoder.api.gov.bc.ca/addresses.json"

#: ``78890-000`` / ``78890000`` / ``78.890-000``
CEP_RE = re.compile(r"^\s*(?:cep\s*:?\s*)?(\d{2})\.?(\d{3})-?(\d{3})\s*$", re.I)
#: ``V1Y 2B3`` / ``v1y2b3`` / ``V1Y-2B3``. No D, F, I, O, Q or U anywhere and no
#: W or Z in first position (Canada Post) — checked so a random six-character
#: word never reads as a postal code.
CA_POSTAL_RE = re.compile(
    r"^\s*([ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z])[\s-]?(\d[ABCEGHJ-NPRSTV-Z]\d)\s*$",
    re.I,
)

#: Nominatim ``addresstype``/``type`` → our precision vocabulary.
_PRECISION_BY_TYPE = {
    "house": "endereco", "building": "endereco", "house_number": "endereco",
    "road": "rua", "street": "rua", "residential": "rua", "primary": "rua",
    "secondary": "rua", "tertiary": "rua", "unclassified": "rua", "track": "rua",
    "trunk": "rua", "service": "rua",
    "postcode": "cep",
    "suburb": "bairro", "neighbourhood": "bairro", "quarter": "bairro",
    "city_district": "bairro", "borough": "bairro", "hamlet": "bairro",
    "city": "cidade", "town": "cidade", "village": "cidade",
    "municipality": "cidade",
    "county": "regiao", "state": "regiao", "region": "regiao",
    "state_district": "regiao", "country": "regiao", "province": "regiao",
}

#: How far to zoom for each precision when there is no useful bounding box.
ZOOM_BY_PRECISION = {
    "endereco": 17, "rua": 16, "cep": 15, "bairro": 14,
    "cidade": 12, "regiao": 8, "lugar": 14,
}

#: Precisions whose bounding box is tighter than a sensible view — these get a
#: centre + zoom and a pin instead of a fitted box.
POINT_PRECISIONS = frozenset({"endereco", "rua", "cep", "lugar"})


class AddressError(RuntimeError):
    """A failure talking to a geocoding service."""


@dataclass(frozen=True)
class Place:
    """A geocoded place. Frames the map; never selects anything."""

    label: str
    lat: float
    lon: float
    #: ``[[south, west], [north, east]]`` — framing a bbox is honest about
    #: uncertainty in a way a single pin is not.
    bounds: Optional[List[List[float]]]
    title: str = ""
    subtitle: str = ""
    precision: str = "lugar"
    attribution: str = OSM_ATTRIBUTION
    source: str = "nominatim"

    def to_hit(self) -> Dict[str, Any]:
        """The plain dict a state var holds (no dataclass crosses the wire)."""
        d = asdict(self)
        d["bounds"] = self.bounds or []
        d["title"] = self.title or self.label
        return d


# --------------------------------------------------------------------------- #
# Recognisers (pure, local — safe on every keystroke)
# --------------------------------------------------------------------------- #
def parse_cep(text: str) -> Optional[str]:
    """``"78890-000"`` → ``"78890000"``; anything else → ``None``."""
    m = CEP_RE.match(text or "")
    return "".join(m.groups()) if m else None


def format_cep(digits: str) -> str:
    return f"{digits[:5]}-{digits[5:]}" if len(digits) == 8 else digits


def parse_ca_postal(text: str) -> Optional[str]:
    """``"v1y2b3"`` → ``"V1Y 2B3"``; anything else → ``None``."""
    m = CA_POSTAL_RE.match(text or "")
    return f"{m.group(1)} {m.group(2)}".upper() if m else None


def looks_like_street_address(text: str) -> bool:
    """A leading civic number followed by words: ``"4700 Lakeshore Rd"``.

    Used only to decide whether the BC register is worth asking first — never
    to reject input.
    """
    return bool(re.match(r"^\s*\d+[A-Za-z]?\s+\S+", text or ""))


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


# --------------------------------------------------------------------------- #
# Labels
# --------------------------------------------------------------------------- #
def _precision_of(item: Dict[str, Any]) -> str:
    for key in (item.get("addresstype"), item.get("type")):
        if key in _PRECISION_BY_TYPE:
            return _PRECISION_BY_TYPE[key]
    if (item.get("address") or {}).get("house_number"):
        return "endereco"
    return "lugar"


def _state_abbrev(address: Dict[str, Any]) -> str:
    """``BR-SP`` → ``SP``, ``CA-BC`` → ``BC``; falls back to the full name."""
    iso = address.get("ISO3166-2-lvl4") or ""
    if "-" in iso:
        return iso.split("-", 1)[1]
    return address.get("state", "")


def describe(item: Dict[str, Any]) -> Tuple[str, str]:
    """A Nominatim ``jsonv2`` result → ``(title, subtitle)``.

    Title is the most specific thing the result *is* (a named place, a road
    with its number, a postcode); subtitle is where it is (neighbourhood,
    town, state). Falls back to splitting ``display_name`` when the result
    carries no address breakdown.
    """
    a = item.get("address") or {}
    name = (item.get("name") or "").strip()
    road = a.get("road") or a.get("pedestrian") or a.get("footway") or ""
    number = a.get("house_number") or ""
    town = (a.get("city") or a.get("town") or a.get("village")
            or a.get("municipality") or a.get("hamlet") or "")
    district = a.get("suburb") or a.get("neighbourhood") or a.get("city_district") or ""
    state = _state_abbrev(a)

    if not a:
        parts = [p.strip() for p in (item.get("display_name") or "").split(",") if p.strip()]
        return (parts[0] if parts else ""), ", ".join(parts[1:4])

    street = ", ".join(p for p in (road, number) if p)
    if name and name not in (road, number, town):
        title = name
        context = [street, district, town]
    elif street:
        title = street
        context = [district, town]
    elif district:
        title = district
        context = [town]
    elif town:
        title = town
        context = [a.get("county", "")]
    else:
        title = name or (item.get("display_name") or "").split(",")[0]
        context = []
    place = ", ".join(p for p in context if p and p != title)
    subtitle = " – ".join(p for p in (place, state) if p)
    return title, subtitle


def _bounds_of(item: Dict[str, Any]) -> Optional[List[List[float]]]:
    bbox = item.get("boundingbox")
    if not bbox or len(bbox) != 4:
        return None
    try:
        s, n, w, e = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return None
    return [[s, w], [n, e]]


# --------------------------------------------------------------------------- #
# The client
# --------------------------------------------------------------------------- #
class AddressGeocoder:
    """One configured client per app (or per country page).

    ``keep`` filters results by coordinate — a Canada page drops the
    occasional cross-border hit ``countrycodes`` lets through, and Yvynation,
    which spans two countries, keeps both.
    """

    def __init__(
        self,
        *,
        url: str,
        user_agent: str,
        accept_language: str,
        countrycodes: str,
        enabled: bool = True,
        timeout: Tuple[float, float] = (10, 20),
        keep: Optional[Callable[[float, float], bool]] = None,
        viewbox: Optional[Tuple[float, float, float, float]] = None,
    ) -> None:
        self.url = url
        self.enabled = enabled
        self.timeout = timeout
        self.countrycodes = countrycodes
        self.keep = keep or (lambda lat, lon: True)
        #: (west, south, east, north) — a ranking hint, never a filter.
        self.viewbox = viewbox
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Accept-Language": accept_language,
        })
        self._lock = threading.Lock()
        self._cache: Dict[str, Any] = {}
        self._cache_lock = threading.Lock()

    # --- plumbing ---------------------------------------------------------
    def _cached(self, key: str, fetch: Callable[[], Any]) -> Any:
        with self._cache_lock:
            if key in self._cache:
                return self._cache[key]
        value = fetch()
        with self._cache_lock:
            self._cache[key] = value
        return value

    def _nominatim(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not self.enabled:
            raise AddressError("geocoder disabled")
        full = {"format": "jsonv2", "addressdetails": 1, **params}
        if "q" in full or "street" in full or "city" in full:
            full.setdefault("countrycodes", self.countrycodes)
        if self.viewbox and "q" in full:
            w, s, e, n = self.viewbox
            full.setdefault("viewbox", f"{w},{n},{e},{s}")

        with self._lock:
            try:
                r = self._session.get(self.url, params=full, timeout=self.timeout)
            except requests.RequestException as exc:
                raise AddressError(str(exc)) from exc
            finally:
                # One request per second is the policy; hold the lock for it
                # rather than trusting callers to pace themselves.
                time.sleep(1.0)
        if r.status_code != 200:
            raise AddressError(f"HTTP {r.status_code}")
        try:
            payload = r.json()
        except ValueError as exc:
            raise AddressError("unexpected response") from exc
        return payload if isinstance(payload, list) else []

    def _to_places(self, items: List[Dict[str, Any]], limit: int) -> List[Place]:
        places: List[Place] = []
        seen: set = set()
        for item in items:
            try:
                lat, lon = float(item["lat"]), float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if not self.keep(lat, lon):
                continue
            title, subtitle = describe(item)
            # Nominatim often returns the same road as several OSM ways; one
            # row per (title, subtitle) is what a person can choose between.
            key = (_norm(title), _norm(subtitle))
            if key in seen:
                continue
            seen.add(key)
            places.append(Place(
                label=item.get("display_name") or title,
                lat=lat, lon=lon, bounds=_bounds_of(item),
                title=title, subtitle=subtitle, precision=_precision_of(item),
            ))
            if len(places) >= limit:
                break
        return places

    # --- public -----------------------------------------------------------
    def search(self, query: str, *, limit: int = 6) -> List[Place]:
        """Free-text place / address search."""
        q = (query or "").strip()
        if not q:
            return []
        return self._cached(
            f"q:{q.lower()}:{limit}",
            lambda: self._to_places(
                self._nominatim({"q": q, "limit": limit * 2}), limit),
        )

    def structured(self, *, limit: int = 4, **fields: str) -> List[Place]:
        """Structured search (``street=``, ``city=``, ``state=``, ``postalcode=``,
        ``country=``) — what a CEP lookup or a postal code needs, because the
        same text as free-form ``q`` is matched far less reliably."""
        clean = {k: v for k, v in fields.items() if v}
        if not clean:
            return []
        key = "s:" + "|".join(f"{k}={v}" for k, v in sorted(clean.items()))
        return self._cached(
            key, lambda: self._to_places(
                self._nominatim({**clean, "limit": limit * 2}), limit))

    # --- Brazil -----------------------------------------------------------
    def lookup_cep(self, digits: str) -> Optional[Dict[str, str]]:
        """ViaCEP → ``{logradouro, bairro, localidade, uf, ibge}``.

        ``None`` for an unknown CEP *and* for a ViaCEP outage — the coordinate
        comes from Nominatim either way, ViaCEP only improves the label, so a
        failure here must never fail the search.
        """
        def fetch() -> Optional[Dict[str, str]]:
            try:
                r = self._session.get(VIACEP_URL.format(cep=digits),
                                      timeout=self.timeout)
                data = r.json() if r.status_code == 200 else None
            except (requests.RequestException, ValueError) as exc:
                logger.info("ViaCEP lookup failed for %s: %s", digits, exc)
                return None
            if not isinstance(data, dict) or data.get("erro"):
                return None
            return {k: str(data.get(k) or "") for k in
                    ("logradouro", "bairro", "localidade", "uf", "ibge")}

        return self._cached(f"cep:{digits}", fetch)

    def search_cep(self, digits: str) -> Tuple[List[Place], Optional[Dict[str, str]]]:
        """A CEP → places, plus ViaCEP's record (for a município fallback).

        Order: Nominatim's postcode table (one request, a centroid for every
        CEP OSM knows), then — only if that is empty — the street ViaCEP names,
        then its município. The first result is relabelled with the street and
        bairro ViaCEP gives, because "01310-100" alone tells a person nothing.
        """
        cep = format_cep(digits)
        info = self.lookup_cep(digits)
        places = self.structured(postalcode=cep, country="Brasil", limit=1)
        if not places and info and info.get("logradouro"):
            places = self.structured(street=info["logradouro"],
                                     city=info["localidade"], state=info["uf"],
                                     country="Brasil", limit=3)
        if not places and info and info.get("localidade"):
            places = self.structured(city=info["localidade"], state=info["uf"],
                                     country="Brasil", limit=1)
        if places and info:
            first = places[0]
            street = info.get("logradouro") or info.get("localidade") or ""
            where = ", ".join(p for p in (info.get("bairro"), info.get("localidade")) if p)
            places = [Place(
                label=first.label, lat=first.lat, lon=first.lon,
                bounds=first.bounds,
                title=f"CEP {cep}" + (f" — {street}" if street else ""),
                subtitle=" – ".join(p for p in (where, info.get("uf")) if p),
                precision="cep",
                attribution=f"{OSM_ATTRIBUTION}; {VIACEP_ATTRIBUTION}",
            )] + places[1:]
        elif places:
            first = places[0]
            places = [Place(
                label=first.label, lat=first.lat, lon=first.lon,
                bounds=first.bounds, title=f"CEP {cep}",
                subtitle=first.subtitle, precision="cep",
            )] + places[1:]
        return places, info

    # --- Canada -----------------------------------------------------------
    def search_ca_postal(self, code: str) -> List[Place]:
        """A Canadian postal code → its centroid (OSM postcode table)."""
        places = self.structured(postalcode=code, country="Canada", limit=1)
        return [Place(
            label=p.label, lat=p.lat, lon=p.lon, bounds=p.bounds,
            title=code, subtitle=p.subtitle, precision="cep",
            attribution=p.attribution,
        ) for p in places]

    def search_bc_address(self, query: str, *, limit: int = 4) -> List[Place]:
        """DataBC's Address Geocoder — civic addresses in British Columbia.

        It always answers *something*: a query from Ontario comes back as a
        score-1 "PROVINCE" match. Only street-level-or-better matches scoring
        70+ are kept, so outside BC this returns ``[]`` and the caller falls
        back to Nominatim without the user ever seeing a junk row. A failure
        is swallowed for the same reason — Nominatim is still asked.
        """
        q = (query or "").strip()
        if not q:
            return []

        def fetch() -> List[Place]:
            try:
                r = self._session.get(BC_GEOCODER_URL, params={
                    "addressString": q, "maxResults": limit, "minScore": 70,
                    "outputSRS": 4326, "echo": "false", "autoComplete": "false",
                }, timeout=self.timeout)
                data = r.json() if r.status_code == 200 else {}
            except (requests.RequestException, ValueError) as exc:
                logger.info("BC geocoder failed for %r: %s", q, exc)
                return []
            out: List[Place] = []
            for f in data.get("features") or []:
                p = f.get("properties") or {}
                precision = {
                    "CIVIC_NUMBER": "endereco", "SITE": "endereco",
                    "UNIT": "endereco", "OCCUPANT": "endereco",
                    "BLOCK": "rua", "STREET": "rua", "INTERSECTION": "rua",
                }.get(p.get("matchPrecision", ""))
                if not precision or (p.get("score") or 0) < 70:
                    continue
                try:
                    lon, lat = f["geometry"]["coordinates"][:2]
                except (KeyError, TypeError, ValueError):
                    continue
                full = p.get("fullAddress") or q
                head, _, tail = full.partition(", ")
                out.append(Place(
                    label=full, lat=float(lat), lon=float(lon), bounds=None,
                    title=head, subtitle=tail, precision=precision,
                    attribution=BC_ATTRIBUTION, source="databc",
                ))
            # An exact civic match makes the register's street-level
            # near-misses ("Lakeshore Pl" for "Lakeshore Rd") noise.
            if any(p.precision == "endereco" for p in out):
                out = [p for p in out if p.precision == "endereco"]
            return out

        return self._cached(f"bc:{q.lower()}:{limit}", fetch)


def merge(*groups: List[Place], limit: int = 8, min_sep_deg: float = 0.0005) -> List[Place]:
    """Concatenate result lists in priority order, dropping near-duplicates
    (~50 m) — the BC register and OSM often both know the same address."""
    out: List[Place] = []
    for group in groups:
        for p in group:
            if any(abs(p.lat - q.lat) < min_sep_deg and abs(p.lon - q.lon) < min_sep_deg
                   for q in out):
                continue
            out.append(p)
            if len(out) >= limit:
                return out
    return out


def attributions(hits: List[Dict[str, Any]]) -> str:
    """The distinct attribution lines of a result list, joined — every source
    shown must be credited, and only the ones actually shown."""
    seen: List[str] = []
    for h in hits:
        for part in str(h.get("attribution") or "").split("; "):
            if part and part not in seen:
                seen.append(part)
    return " · ".join(seen)


__all__ = [
    "AddressError", "AddressGeocoder", "Place", "POINT_PRECISIONS",
    "ZOOM_BY_PRECISION", "attributions", "describe", "format_cep", "merge",
    "looks_like_street_address", "parse_ca_postal", "parse_cep",
]
