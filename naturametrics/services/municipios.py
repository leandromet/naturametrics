"""The município list — local, committed, instant.

Ported from camposcope's module of the same name. The *list* is a CSV in
``data/`` (``scripts/fetch_municipios.py``); the *geometry* comes from the
same Earth Engine asset camposcope's own search reads
(``config/datasets.py::IBGE_MUNICIPIOS`` — both apps run under the
ee-leandromet project, so this is a read-only reference to an asset this app
does not own). ``cod_municipio_ibge`` joins the two.

Used only by services/geocode.py's município resolver, to let the search box
frame the map on a chosen município without a network round trip for every
keystroke — only the one-off ``bounds()`` call, once a município is actually
picked, touches Earth Engine at all.
"""

from __future__ import annotations

import csv
import logging
import pathlib
import threading
import unicodedata
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA = (pathlib.Path(__file__).resolve().parent.parent.parent
         / "data" / "municipios.csv")

_lock = threading.Lock()
_rows: Optional[List[Dict[str, Any]]] = None
_by_code: Optional[Dict[int, Dict[str, Any]]] = None


def normalise(name: str) -> str:
    """Accent- and case-folded, matching ``scripts/fetch_municipios.py``.

    Users type "sao felix" for "São Félix"; both must find the same município.
    """
    decomposed = unicodedata.normalize("NFKD", name or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _load() -> List[Dict[str, Any]]:
    global _rows, _by_code
    if _rows is None:
        with _lock:
            if _rows is None:
                if not _DATA.exists():
                    raise FileNotFoundError(
                        f"{_DATA} não encontrado. Rode "
                        "`python scripts/fetch_municipios.py`."
                    )
                with _DATA.open(encoding="utf-8", newline="") as fh:
                    rows = [
                        {
                            "cod_municipio_ibge": int(r["cod_municipio_ibge"]),
                            "nome": r["nome"],
                            "uf": r["uf"],
                            "nome_norm": r["nome_norm"],
                        }
                        for r in csv.DictReader(fh)
                    ]
                _rows = rows
                _by_code = {r["cod_municipio_ibge"]: r for r in rows}
                logger.info("municípios loaded: %d", len(rows))
    return _rows


def _for_uf(uf: str) -> List[Dict[str, Any]]:
    """Every município in a UF — used by search() to narrow a "Nome/UF" query."""
    key = (uf or "").strip().upper()
    return [r for r in _load() if r["uf"] == key]


def by_code(cod_municipio_ibge: int) -> Optional[Dict[str, Any]]:
    _load()
    return (_by_code or {}).get(int(cod_municipio_ibge))


def search(text: str, *, uf: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Type-ahead over município names.

    Accepts ``"Vera"``, ``"vera/MT"`` and ``"Vera, Mato Grosso"``-style input by
    splitting a trailing UF off the query. Prefix matches rank above substring
    matches, because a user typing "cuia" means Cuiabá and not "Aracuia".
    """
    raw = (text or "").strip()
    if not raw:
        return []

    # A trailing "/MT" or ", MT" narrows the search rather than breaking it.
    for sep in ("/", ","):
        if sep in raw:
            head, _, tail = raw.rpartition(sep)
            candidate = tail.strip().upper()
            if len(candidate) == 2 and head.strip():
                raw, uf = head.strip(), candidate
                break

    needle = normalise(raw)
    rows = _for_uf(uf) if uf else _load()

    prefix = [r for r in rows if r["nome_norm"].startswith(needle)]
    if len(prefix) >= limit:
        return prefix[:limit]

    seen = {r["cod_municipio_ibge"] for r in prefix}
    substring = [
        r for r in rows
        if needle in r["nome_norm"] and r["cod_municipio_ibge"] not in seen
    ]
    return (prefix + substring)[:limit]


# --------------------------------------------------------------------------- #
# Geometry — from Earth Engine
# --------------------------------------------------------------------------- #
_geom_cache: Dict[int, Dict[str, Any]] = {}


def geometry(cod_municipio_ibge: int) -> Optional[Dict[str, Any]]:
    """The município boundary as GeoJSON, for framing the map.

    The *list* is local and instant; only the *geometry* costs a round trip, and
    only when a município is actually chosen. Cached for the process lifetime —
    a municipal boundary does not move.

    ``CD_MUN`` is a **string** in the asset, so the filter compares strings.
    Passing an integer silently matches nothing.
    """
    code = int(cod_municipio_ibge)
    if code in _geom_cache:
        return _geom_cache[code]

    import ee

    from ..config.datasets import IBGE_MUNICIPIOS
    from .ee_client import get_ee

    asset = IBGE_MUNICIPIOS["asset"]
    if not asset:
        return None

    get_ee()
    field = IBGE_MUNICIPIOS["fields"]["code"]
    fc = ee.FeatureCollection(asset).filter(ee.Filter.eq(field, str(code)))
    try:
        info = fc.first().getInfo()
    except Exception as exc:                       # noqa: BLE001
        logger.warning("município geometry lookup failed for %s: %s", code, exc)
        return None
    if not info:
        logger.warning("município %s not found in %s", code, asset)
        return None

    geom = info.get("geometry")
    _geom_cache[code] = geom
    return geom


def bounds(cod_municipio_ibge: int) -> Optional[List[List[float]]]:
    """``[[south, west], [north, east]]`` for framing the map."""
    geom = geometry(cod_municipio_ibge)
    if not geom:
        return None
    from shapely.geometry import shape

    minx, miny, maxx, maxy = shape(geom).bounds
    return [[miny, minx], [maxy, maxx]]


__all__ = ["by_code", "search", "normalise", "geometry", "bounds"]
