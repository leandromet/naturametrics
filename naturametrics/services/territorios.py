"""Terras indígenas (FUNAI) and unidades de conservação (CNUC/ICMBio).

Two things live here, and they are deliberately separate:

**The list** — ``data/territorios.csv``, 3 904 rows of name, code, UF, area and
bounding box. It is what the search box matches against, and it is local,
committed and instant for the same reason the município list is: a type-ahead
must not wait on a round trip, and framing the map on a hit must not wait on a
polygon. The bbox in each row is computed from the
*original* geometry, so framing is exact even though the overlay is not.

**The overlay** — two pre-gzipped, pre-simplified GeoJSON files, served to the
browser by an ordinary HTTP GET (``naturametrics/api``) rather than pushed through
the WebSocket, exactly as :mod:`naturametrics.services.biomes` explains for the
biome polygons. Same reason these are vectors and every raster layer is a tile:
each polygon has to name itself on hover and carry a permanent on-map label,
and a tile is pixels.

Both artefacts are built offline by ``scripts/fetch_territorios.py`` and
committed. Unlike the biome layer there is no Earth Engine asset to rebuild
them from at runtime: the sources are GeoPackages, and reading one needs
geopandas/fiona, which are deliberately absent from this app's dependencies
(doc/08-dev-environment.md §3).

**Orientation, not determination.** The drawn boundaries are simplified to
~200 m. They must never be used to decide whether a property or a coordinate
falls inside a terra indígena or a unidade de conservação, and nothing here
does — the layers draw, label and name themselves, and that is all.
"""

from __future__ import annotations

import csv
import gzip
import logging
import pathlib
import threading
import unicodedata
from typing import Any, Dict, List, Optional

from ..config.datasets import TERRITORIOS

logger = logging.getLogger(__name__)

_DATA = pathlib.Path(__file__).resolve().parent.parent.parent / "data"
_CSV = _DATA / "territorios.csv"

#: The two ``tipo`` values, in the order the UI offers them.
TIPOS = ("indigena", "conservacao")

_lock = threading.Lock()
_rows: Optional[List[Dict[str, Any]]] = None
_by_key: Optional[Dict[str, Dict[str, Any]]] = None

_geojson_lock = threading.Lock()
_geojson_memo: Dict[str, bytes] = {}


def normalise(name: str) -> str:
    """Accent- and case-folded, matching ``scripts/fetch_territorios.py``.

    Users type "raposa serra do sol" for "Raposa Serra do Sol"; both must find
    the same territory.
    """
    decomposed = unicodedata.normalize("NFKD", name or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _key(tipo: str, codigo: str) -> str:
    """``tipo:codigo`` — the identifier the UI passes around.

    A name is not unique (11 terras indígenas and 34 unidades de conservação
    share a name with another of their own kind) and a code is only unique
    *within* its type, so neither alone can address a row.
    """
    return f"{tipo}:{codigo}"


def _load() -> List[Dict[str, Any]]:
    global _rows, _by_key
    if _rows is None:
        with _lock:
            if _rows is None:
                if not _CSV.exists():
                    raise FileNotFoundError(
                        f"{_CSV} não encontrado. Rode "
                        "`python scripts/fetch_territorios.py`."
                    )
                with _CSV.open(encoding="utf-8", newline="") as fh:
                    rows = [
                        {
                            "tipo": r["tipo"],
                            "codigo": r["codigo"],
                            "nome": r["nome"],
                            "nome_norm": r["nome_norm"],
                            "uf": r["uf"],
                            "area_ha": float(r["area_ha"] or 0),
                            "detalhe": r["detalhe"],
                            # ``[[south, west], [north, east]]`` — the shape
                            # state/_layers.py::fit_bounds already speaks.
                            "bounds": [
                                [float(r["sul"]), float(r["oeste"])],
                                [float(r["norte"]), float(r["leste"])],
                            ],
                        }
                        for r in csv.DictReader(fh)
                    ]
                _rows = rows
                _by_key = {_key(r["tipo"], r["codigo"]): r for r in rows}
                logger.info("territórios loaded: %d", len(rows))
    return _rows


def by_key(key: str) -> Optional[Dict[str, Any]]:
    _load()
    return (_by_key or {}).get(key)


def bounds(key: str) -> Optional[List[List[float]]]:
    """``[[south, west], [north, east]]`` for framing the map.

    Straight out of the committed row — no Earth Engine call, no geometry
    parse, unlike ``municipios.bounds``. The bbox was computed from the full
    unsimplified polygon, so framing is exact even where the overlay is coarse.
    """
    row = by_key(key)
    return list(row["bounds"]) if row else None


def search(text: str, *, tipo: Optional[str] = None,
           limit: int = 8) -> List[Dict[str, Any]]:
    """Type-ahead over territory names.

    Prefix matches rank above substring matches, for the same reason
    ``municipios.search`` orders them that way: a user typing "yano" means
    Yanomami, not "Alto Rio Yanomami" further down someone else's list. Ties
    inside each band break on area, largest first — with 3 247 unidades de
    conservação, an eight-row list that leads with the RPPNs would be useless.

    Accepts a trailing UF the same way the município search does: ``"kayapó/PA"``
    and ``"kayapó, PA"`` both narrow to Pará.
    """
    raw = (text or "").strip()
    if not raw:
        return []

    uf: Optional[str] = None
    for sep in ("/", ","):
        if sep in raw:
            head, _, tail = raw.rpartition(sep)
            candidate = tail.strip().upper()
            if len(candidate) == 2 and candidate.isalpha() and head.strip():
                raw, uf = head.strip(), candidate
                break

    needle = normalise(raw)
    # Two characters is where a substring pass over 3 900 names stops being a
    # search and starts being the whole list.
    if len(needle) < 2:
        return []

    rows = _load()
    if tipo:
        rows = [r for r in rows if r["tipo"] == tipo]
    if uf:
        rows = [r for r in rows if uf in r["uf"].split(", ")]

    def rank(row: Dict[str, Any]) -> tuple:
        return (0 if row["nome_norm"].startswith(needle) else 1, -row["area_ha"])

    hits = [r for r in rows if needle in r["nome_norm"]]
    hits.sort(key=rank)
    return hits[:limit]


def count(tipo: str) -> int:
    return sum(1 for r in _load() if r["tipo"] == tipo)


# --------------------------------------------------------------------------- #
# The overlay geometry
# --------------------------------------------------------------------------- #
def geojson_gzipped(tipo: str) -> bytes:
    """The simplified polygons for one type, gzip-compressed, memoised.

    One tier fewer than :func:`biomes.geojson_gzipped`: there is no Earth
    Engine round trip and no cache to build, because the file is committed
    already gzipped in exactly the form the HTTP route serves. Re-compressing
    it per request, or even per process, would be pure waste.
    """
    conf = TERRITORIOS[tipo]
    with _geojson_lock:
        memo = _geojson_memo.get(tipo)
    if memo is not None:
        return memo

    path = _DATA / conf["data_file"]
    if not path.exists():
        raise FileNotFoundError(
            f"{path} não encontrado. Rode `python scripts/fetch_territorios.py`."
        )
    payload = path.read_bytes()
    with _geojson_lock:
        _geojson_memo[tipo] = payload
    logger.info("%s GeoJSON ready: %s KiB gzipped", tipo, len(payload) // 1024)
    return payload


def geojson_plain(tipo: str) -> bytes:
    """The same payload decompressed — for the rare client that refuses gzip."""
    return gzip.decompress(geojson_gzipped(tipo))


# --------------------------------------------------------------------------- #
# Layer specs
# --------------------------------------------------------------------------- #
#: Paths served by the backend (see :mod:`naturametrics.api`). Relative — the map
#: component resolves them against the backend origin, which differs between
#: the split dev ports and single-port production.
GEOJSON_PATHS = {
    "indigena": "/_terras_indigenas.geojson",
    "conservacao": "/_unidades_conservacao.geojson",
}

#: 3 247 unidades de conservação worth of names is an unreadable mat at the
#: scale of a whole state — this is the zoom level (leaflet_map.js's
#: applyLabelVisibility) below which labels are hidden regardless of the "show
#: labels" toggle. One step tighter than the biome layer's 7: there are an
#: order of magnitude more of these, and they are far smaller.
LABEL_MIN_ZOOM = 8


def vector_spec(tipo: str, *, opacity: float = 0.35, z_index: int = 6,
                show_labels: bool = True) -> Dict[str, Any]:
    """Spec for one browser-side territory layer.

    Purely declarative and involves no Earth Engine call, so unlike every tile
    spec it cannot fail — the fetch happens in the browser.

    ``z_index`` is carried for symmetry with the tile specs and with
    ``biomes.vector_spec``; it orders nothing. Every vector layer shares one
    Leaflet pane (``nmVectors``) and they stack in the order the caller lists
    them — see the state's territory-vector builder.
    """
    conf = TERRITORIOS[tipo]
    return {
        # The labels suffix makes "show labels" part of the layer's identity,
        # for the reason services/biomes.py sets out at length: label markers
        # are built once, at build time, so toggling the flag has to force
        # leaflet_map.js to rebuild the layer rather than patch it in place.
        "id": f"territorios:{tipo}:{'lbl' if show_labels else 'nolbl'}",
        "path": GEOJSON_PATHS[tipo],
        "opacity": opacity,
        "z_index": z_index,
        "attribution": conf["attribution"],
        # No `color_property`: one layer, one hue. styleFor falls straight
        # through to `default_color` when the palette has nothing to say.
        "default_color": conf["color"],
        "weight": conf["outline_width"],
        "label_property": conf["label_property"] if show_labels else None,
        "label_min_zoom": LABEL_MIN_ZOOM,
        "tooltip": list(conf["tooltip"]),
    }


__all__ = [
    "TIPOS", "GEOJSON_PATHS", "LABEL_MIN_ZOOM",
    "search", "by_key", "bounds", "count", "normalise",
    "geojson_gzipped", "geojson_plain", "vector_spec",
]
