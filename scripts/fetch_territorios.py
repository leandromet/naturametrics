"""Build the committed territory artefacts: ``data/territorios.csv`` and the two
simplified polygon files served to the browser.

Offline prep, run rarely, never imported by the app — the same shape as
``scripts/fetch_municipios.py`` and ``scripts/fetch_ifn.py``.

What it produces
----------------
``data/territorios.csv``
    One row per territory — name, code, UF, area and **bounding box**. This is
    the whole of what the search box needs: the type-ahead matches names
    locally with no round trip (constraint C5, exactly as the município list
    does), and framing the map on a hit reads the bbox straight out of this
    row rather than parsing a polygon. ~3 900 rows, ~500 KiB.

``data/terras_indigenas.geojson.gz`` and ``data/unidades_conservacao.geojson.gz``
    The map overlays, simplified, pre-gzipped in exactly the form
    ``naturametrics/api`` serves them (services/territorios.py never
    re-compresses).

Why the artefacts are committed rather than built at runtime
------------------------------------------------------------
The sources are two GeoPackages, and neither ``geopandas`` nor ``fiona`` is a
runtime dependency of this app — deliberately (doc/08-dev-environment.md §3).
This script does not need them either: a GeoPackage *is* a SQLite database and
its geometry column is WKB behind a small documented header, so ``sqlite3`` and
``shapely`` (both already here) read it directly. Committing the outputs is
the same call ``data/ifn_points.csv`` already makes under the data policy in
``data/README.md``: small, static, derived, and a deploy cannot rebuild it —
the Dockerfile builds from the git checkout, and the source GeoPackages are
not in this repo.

Accuracy
--------
Simplified to ~200 m and rounded to three decimal places (~110 m, matched to
the simplification so the rounding never adds error the simplification did not
already allow). **These boundaries are orientation, not a determination**: they
must never decide whether a given property or coordinate falls inside a
protected area or an indigenous land. Nothing in this app asks them to — the
layers draw and label themselves, and that is all.

Sources
-------
* FUNAI — Terras Indígenas (poligonais e portarias).
* MMA/ICMBio — Cadastro Nacional de Unidades de Conservação (CNUC).

Usage
-----
    python scripts/fetch_territorios.py \
        --indigenous /path/to/indigenous_lands_br202605.gpkg \
        --conservation /path/to/environment_conservation_br202605.gpkg
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import pathlib
import sqlite3
import sys
import unicodedata
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from shapely import wkb
from shapely.geometry import mapping

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

#: Simplification tolerance in metres, and the matching coordinate precision —
#: the same pairing services/biomes.py documents, at a tenth of its tolerance
#: because a terra indígena can be a few hundred hectares where a biome never is.
SIMPLIFY_M = 200
COORD_DECIMALS = 3

#: One degree of latitude, near enough, for turning the metre tolerance above
#: into the degrees shapely's ``simplify`` actually works in. Longitude degrees
#: shrink toward the poles, so this over-simplifies slightly in the far south —
#: at Brazil's southern limit (~33°S) by a factor of cos(33°) ≈ 0.84, which is
#: 170 m instead of 200 m. Immaterial for a layer that is orientation only.
_M_PER_DEGREE = 111_320.0

#: ``[[south, west], [north, east]]`` is what the map wants; the CSV stores the
#: four numbers flat so a row stays a row.
_BBOX_FIELDS = ("sul", "oeste", "norte", "leste")

CSV_FIELDS = ("tipo", "codigo", "nome", "nome_norm", "uf", "area_ha",
              "detalhe", *_BBOX_FIELDS)


# --------------------------------------------------------------------------- #
# GeoPackage reading — sqlite3 + shapely, no geopandas
# --------------------------------------------------------------------------- #
def _gpkg_geometry(blob: Optional[bytes]):
    """Decode one GeoPackage geometry blob.

    The format (OGC GeoPackage §2.1.3) is a fixed 8-byte header — magic ``GP``,
    version, flags, srs_id — then an optional envelope whose length the flags
    encode, then plain WKB. Only the envelope length has to be read; everything
    after it is what shapely already understands.
    """
    if not blob:
        return None
    if blob[:2] != b"GP":
        raise ValueError(f"not a GeoPackage geometry blob: {blob[:4]!r}")
    envelope = (blob[3] >> 1) & 0x07
    try:
        skip = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[envelope]
    except KeyError:
        raise ValueError(f"reserved envelope indicator {envelope}") from None
    return wkb.loads(blob[8 + skip:])


def _rows(path: pathlib.Path, layer: str, columns: Tuple[str, ...]) -> Iterator[Dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"GeoPackage not found: {path}")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        select = ", ".join(f'"{c}"' for c in (*columns, "geom"))
        for row in con.execute(f'SELECT {select} FROM "{layer}"'):
            yield dict(row)
    finally:
        con.close()


# --------------------------------------------------------------------------- #
# Geometry cleanup — ported from services/biomes.py, same reasoning
# --------------------------------------------------------------------------- #
def _clean_ring(ring: list, dp: int) -> Optional[list]:
    """Round a ring and drop the duplicate vertices rounding creates.

    Without the dedup, rounding *adds* bytes: long stretches of boundary
    collapse onto the same rounded coordinate and each repeat still costs its
    characters. A ring needs 4 positions to close; anything shorter is a sliver
    the simplification has already destroyed.
    """
    out: List[List[float]] = []
    for x, y in ring:
        pos = [round(x, dp), round(y, dp)]
        if not out or out[-1] != pos:
            out.append(pos)
    if len(out) < 4:
        return None
    if out[0] != out[-1]:
        out.append(list(out[0]))
    return out


def _clean_geometry(geom: dict, dp: int) -> Optional[dict]:
    """Reduce any geometry to a Polygon/MultiPolygon, or drop it.

    ``simplify`` turns the smallest islands into LineStrings and Points, and
    Leaflet would render the degenerate ones as invisible zero-area shapes that
    still sit in the hit-test path and steal hovers from the polygon
    underneath.
    """
    kind = geom.get("type")

    if kind == "Polygon":
        rings = [r for r in (_clean_ring(r, dp) for r in geom["coordinates"]) if r]
        return {"type": "Polygon", "coordinates": rings} if rings else None

    if kind == "MultiPolygon":
        polys = []
        for poly in geom["coordinates"]:
            rings = [r for r in (_clean_ring(r, dp) for r in poly) if r]
            if rings:
                polys.append(rings)
        return {"type": "MultiPolygon", "coordinates": polys} if polys else None

    if kind == "GeometryCollection":
        parts = [g for g in (_clean_geometry(g, dp) for g in geom.get("geometries", [])) if g]
        if not parts:
            return None
        polys: list = []
        for part in parts:
            if part["type"] == "MultiPolygon":
                polys.extend(part["coordinates"])
            else:
                polys.append(part["coordinates"])
        return {"type": "MultiPolygon", "coordinates": polys}

    return None  # Point, LineString — degenerate remains of simplification


# --------------------------------------------------------------------------- #
# Attribute normalisation
# --------------------------------------------------------------------------- #
def normalise(name: str) -> str:
    """Accent- and case-folded, matching ``services/municipios.py::normalise``.

    Users type "raposa serra do sol" for "Raposa Serra do Sol"; both must find
    the same territory. Duplicated rather than imported so this script stays
    runnable without the app package on the path.
    """
    decomposed = unicodedata.normalize("NFKD", name or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


# --------------------------------------------------------------------------- #
# Map labels
# --------------------------------------------------------------------------- #
#: Words that carry no identity in a CNUC name — the 12 CNUC categories broken
#: into words, their administrative qualifiers, and the Portuguese connectors
#: that glue them to the actual name.
#:
#: Why strip them at all: the on-map label is a ~92 px wrapped block
#: (``components/map/leaflet_map.py``'s ``.cs-vector-label``), and "RESERVA
#: PARTICULAR DO PATRIMÔNIO NATURAL TOCA FURADA" wraps to eight lines of which
#: seven say only what the swatch and the tooltip already say. "Toca Furada"
#: is one line and is the part that distinguishes this unit from the 1 286
#: other RPPNs. The full official name is untouched everywhere it matters —
#: the search list, the hover tooltip and ``territorios.csv`` all keep it.
_GENERIC_WORDS = {
    # the categories
    "RESERVA", "PARTICULAR", "PATRIMONIO", "NATURAL", "PARQUE", "AREA",
    "PROTECAO", "AMBIENTAL", "REFUGIO", "VIDA", "SILVESTRE", "MONUMENTO",
    "ESTACAO", "ECOLOGICA", "RELEVANTE", "INTERESSE", "ECOLOGICO", "FLORESTA",
    "EXTRATIVISTA", "BIOLOGICA", "DESENVOLVIMENTO", "SUSTENTAVEL", "FAUNA",
    # administrative qualifiers
    "NACIONAL", "ESTADUAL", "MUNICIPAL", "DISTRITAL", "FEDERAL", "MARINHO",
    "MARINHA", "BOTANICO", "BOTANICA", "HORTO",
}

#: Kept lowercase when a stripped name is title-cased back into prose.
_CONNECTORS = {"da", "de", "do", "das", "dos", "e", "no", "na", "em", "sob"}

#: Kept ALL CAPS through the title-casing. An allowlist rather than a
#: "short and uppercase" rule, which every name is: that rule turned "RIO
#: IRATAPURU" into "RIO Iratapuru" and "LAR DOS IDOSOS" into "LAR dos Idosos".
_ACRONYMS = {"RPPN", "APA", "ARIE", "ESEC", "FLONA", "REBIO", "RESEX", "RDS",
             "REVIS", "PARNA", "MONA", "SP", "RJ", "MG", "DF"}


def _label(nome: str, strip_generic: bool) -> str:
    """The short name the map draws over a polygon.

    Terras indígenas pass through untouched — FUNAI's names are already short
    and already mixed case. CNUC names are ALL CAPS and lead with their
    category, so both are undone here.
    """
    raw = " ".join((nome or "").split())
    if not raw:
        return ""
    if not strip_generic:
        return raw

    words = raw.split(" ")
    start = 0
    while start < len(words):
        folded = normalise(words[start]).upper()
        if folded in _GENERIC_WORDS or folded.lower() in _CONNECTORS:
            start += 1
            continue
        break
    # Everything was generic ("PARQUE NACIONAL", say, with no distinguishing
    # part at all) — the full name is the honest fallback, since a label has
    # to say something.
    stripped = words[start:] or words

    out = []
    for i, word in enumerate(stripped):
        lower = word.lower()
        if i and lower in _CONNECTORS:
            out.append(lower)
        elif word.upper() in _ACRONYMS:
            out.append(word.upper())
        else:
            out.append(lower.capitalize() if word.isupper() else word)
    return " ".join(out)


#: The CNUC ``uf`` column stores full state names (comma-separated for a unit
#: spanning several), where FUNAI's stores siglas. One vocabulary in the output.
_UF_NAME_TO_SIGLA = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPÁ": "AP", "AMAZONAS": "AM",
    "BAHIA": "BA", "CEARÁ": "CE", "DISTRITO FEDERAL": "DF",
    "ESPÍRITO SANTO": "ES", "GOIÁS": "GO", "MARANHÃO": "MA",
    "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS", "MINAS GERAIS": "MG",
    "PARÁ": "PA", "PARAÍBA": "PB", "PARANÁ": "PR", "PERNAMBUCO": "PE",
    "PIAUÍ": "PI", "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN",
    "RIO GRANDE DO SUL": "RS", "RONDÔNIA": "RO", "RORAIMA": "RR",
    "SANTA CATARINA": "SC", "SÃO PAULO": "SP", "SERGIPE": "SE",
    "TOCANTINS": "TO",
}


def _ufs(raw: Any) -> str:
    """Comma-separated siglas, whichever vocabulary the source used."""
    out: List[str] = []
    for part in str(raw or "").split(","):
        name = part.strip().upper()
        if not name:
            continue
        if len(name) == 2 and name.isalpha():
            out.append(name)
        else:
            sigla = _UF_NAME_TO_SIGLA.get(name)
            if sigla and sigla not in out:
                out.append(sigla)
    return ", ".join(out)


def _area_ha(raw: Any) -> float:
    """Coerce an area to a finite float.

    CNUC stores ``ha_total`` as TEXT with a comma decimal separator, and a
    handful of rows carry a literal NaN — which ``float()`` passes through
    silently and which then breaks every ``>=``/``<=`` comparison downstream,
    since NaN compares False against everything.
    """
    try:
        value = float(str(raw or 0).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0
    return round(value, 2) if value == value else 0.0


# --------------------------------------------------------------------------- #
# The two sources
# --------------------------------------------------------------------------- #
class Source:
    """One GeoPackage layer, and how to read a territory out of a row of it."""

    def __init__(self, tipo: str, layer: str, columns: Tuple[str, ...],
                 to_record: Callable[[Dict[str, Any]], Dict[str, Any]],
                 out_geojson: str):
        self.tipo = tipo
        self.layer = layer
        self.columns = columns
        self.to_record = to_record
        self.out_geojson = out_geojson


def _indigenous_record(row: Dict[str, Any]) -> Dict[str, Any]:
    # `fase_ti` is the demarcation stage (Declarada, Homologada, Regularizada,
    # …) — the single most load-bearing attribute a terra indígena has, and the
    # one a reader most needs beside the name.
    fase = (row.get("fase_ti") or "").strip()
    etnia = (row.get("etnia_nome") or "").strip()
    return {
        "codigo": str(row.get("terrai_cod") or "").strip(),
        "nome": (row.get("terrai_nom") or "").strip(),
        "uf": _ufs(row.get("uf_sigla")),
        "area_ha": _area_ha(row.get("superficie")),
        "detalhe": " · ".join(p for p in (fase, etnia) if p),
        "properties": {
            "nome": (row.get("terrai_nom") or "").strip(),
            "rotulo": _label(row.get("terrai_nom") or "", strip_generic=False),
            "etnia": etnia,
            "fase": fase,
            "uf": _ufs(row.get("uf_sigla")),
            "municipios": (row.get("municipio_") or "").strip(),
        },
    }


def _conservation_record(row: Dict[str, Any]) -> Dict[str, Any]:
    categoria = (row.get("categoria") or "").strip()
    esfera = (row.get("esfera") or "").strip()
    return {
        "codigo": str(row.get("cd_cnuc") or "").strip(),
        "nome": (row.get("nome_uc") or "").strip(),
        "uf": _ufs(row.get("uf")),
        "area_ha": _area_ha(row.get("ha_total")),
        "detalhe": " · ".join(p for p in (categoria, esfera) if p),
        "properties": {
            "nome": (row.get("nome_uc") or "").strip(),
            "rotulo": _label(row.get("nome_uc") or "", strip_generic=True),
            "categoria": categoria,
            "grupo": (row.get("grupo") or "").strip(),
            "esfera": esfera,
            "gestor": (row.get("org_gestor") or "").strip(),
            "uf": _ufs(row.get("uf")),
        },
    }


SOURCES = {
    "indigena": Source(
        tipo="indigena",
        layer="tis_poligonais_portarias",
        columns=("terrai_cod", "terrai_nom", "etnia_nome", "municipio_",
                 "uf_sigla", "superficie", "fase_ti"),
        to_record=_indigenous_record,
        out_geojson="terras_indigenas.geojson.gz",
    ),
    "conservacao": Source(
        tipo="conservacao",
        layer="cnuc",
        columns=("cd_cnuc", "nome_uc", "uf", "ha_total", "esfera", "grupo",
                 "categoria", "org_gestor"),
        to_record=_conservation_record,
        out_geojson="unidades_conservacao.geojson.gz",
    ),
}


# --------------------------------------------------------------------------- #
def build(source: Source, gpkg: pathlib.Path) -> List[Dict[str, Any]]:
    """Write one source's GeoJSON and return its CSV rows."""
    tolerance = SIMPLIFY_M / _M_PER_DEGREE
    features: List[Dict[str, Any]] = []
    csv_rows: List[Dict[str, Any]] = []
    dropped = 0
    undrawable = 0

    for row in _rows(gpkg, source.layer, source.columns):
        geom = _gpkg_geometry(row.get("geom"))
        record = source.to_record(row)
        if geom is None or geom.is_empty or not record["nome"]:
            dropped += 1
            continue

        simplified = geom.simplify(tolerance, preserve_topology=True)
        # preserve_topology keeps a valid shape, but a unit smaller than one
        # rounding cell still collapses to fewer than the 4 positions a ring
        # needs — 13 CNUC units of 0.01-2.5 ha do, at the 2026-05 snapshot.
        # Those keep their CSV row (searchable, and its bbox still frames the
        # map on them) and simply contribute no polygon to the overlay: a
        # sub-hectare shape is invisible at any zoom this layer is legible at,
        # and an invisible zero-area shape in the hit-test path steals hovers
        # from whatever is underneath it.
        cleaned = _clean_geometry(mapping(simplified), COORD_DECIMALS)
        if cleaned is None:
            cleaned = _clean_geometry(mapping(geom), COORD_DECIMALS)
        if cleaned is None:
            undrawable += 1

        # The bbox comes from the ORIGINAL geometry, not the simplified one:
        # it is what frames the map on a search hit, and framing must not
        # inherit the overlay's deliberate coarseness.
        west, south, east, north = geom.bounds

        if cleaned is not None:
            properties = dict(record["properties"])
            properties["codigo"] = record["codigo"]
            properties["area_ha"] = record["area_ha"]
            features.append({
                "type": "Feature",
                "properties": properties,
                "geometry": cleaned,
            })
        csv_rows.append({
            "tipo": source.tipo,
            "codigo": record["codigo"],
            "nome": record["nome"],
            "nome_norm": normalise(record["nome"]),
            "uf": record["uf"],
            "area_ha": record["area_ha"],
            "detalhe": record["detalhe"],
            "sul": round(south, 5),
            "oeste": round(west, 5),
            "norte": round(north, 5),
            "leste": round(east, 5),
        })

    body = json.dumps({"type": "FeatureCollection", "features": features},
                      separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload = gzip.compress(body, 9)
    out = DATA / source.out_geojson
    out.write_bytes(payload)
    print(f"  {out.name}: {len(features)} features, "
          f"{len(body) / 1e6:.1f} MB raw, {len(payload) / 1e6:.2f} MB gzipped"
          + (f", {undrawable} listed but too small to draw" if undrawable else "")
          + (f", {dropped} dropped" if dropped else ""))
    return csv_rows


def main() -> int:
    default = (pathlib.Path("/run/media/leandrobiondo/Windows/github_linux")
               / "yvynation" / "reflex_app" / "yvynation" / "utils")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--indigenous", type=pathlib.Path,
                        default=default / "indigenous_lands_br202605.gpkg",
                        help="FUNAI terras indígenas GeoPackage")
    parser.add_argument("--conservation", type=pathlib.Path,
                        default=default / "environment_conservation_br202605.gpkg",
                        help="CNUC unidades de conservação GeoPackage")
    args = parser.parse_args()

    DATA.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    for source, gpkg in ((SOURCES["indigena"], args.indigenous),
                         (SOURCES["conservacao"], args.conservation)):
        print(f"{source.tipo}: reading {gpkg} …")
        rows.extend(build(source, gpkg))

    # Sorted by name within type, so the file is diffable between refreshes
    # and the search's own ordering has a stable starting point.
    rows.sort(key=lambda r: (r["tipo"], r["nome_norm"], r["codigo"]))
    out = DATA / "territorios.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(CSV_FIELDS))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {out.name}: {len(rows)} rows, {out.stat().st_size / 1e3:.0f} KiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
