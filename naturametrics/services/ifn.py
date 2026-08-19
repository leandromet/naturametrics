"""IFN sampling points as a filterable Earth Engine layer.

The full national conglomerado grid lives in our own Earth Engine asset
(``config.datasets.IFN_POINTS``): 17 495 features, of which **17 479 are usable**
— 16 carry an empty MultiPoint geometry and no attributes, and can be neither
drawn nor filtered. It is rendered the same way every
other layer is: Earth Engine paints it, mints a tile URL, and the browser fetches
tiles directly (decision D1). Nothing about the point set travels over the
WebSocket, which is what makes a national grid affordable at all — the same set
as GeoJSON is several megabytes per filter change.

**Filtering.** All four filters are ordinary ``ee.Filter.eq``, because the layer
reads the *joined* asset (``config.datasets.IFN_POINTS_JOINED``) in which the
biome is already a property.

That indirection is not tidiness. Filtering the raw SFB points spatially, with
``filterBounds`` against a biome outline, works for Pantanal, Pampa and Caatinga
and fails for Amazônia, Cerrado and Mata Atlântica with *"Description length
exceeds maximum"* — those three outlines are too long for Earth Engine's filter
machinery at 1:250 000, and passing the collection instead of its geometry does
not change that. Simplifying the outline would fix the request and quietly
misassign every point near a boundary. So the intersection is done once, by
``scripts/join_ifn_biomes.py --export-asset``, and stored.

**Everything the UI needs to answer about a filter is precomputed.** The option
lists, the point count and the extent to frame all come from
``data/ifn_filter_index.csv``, written by the same script from the same join. So
choosing a filter costs no round trip at all — the dropdowns cascade, the count
updates and the map frames the selection from a 330 KiB table held in memory,
and Earth Engine is asked for exactly one thing: the tiles. The index and the
asset cannot disagree; they are two outputs of one join.

Every distinct filter combination is a distinct tile URL and is cached under a
key that spells the combination out, so going back to a previous filter is free.
"""

from __future__ import annotations

import csv
import logging
import threading
from typing import Any, Iterable

from ..config import datasets as ds
from ..config.settings import IFN_FILTER_INDEX_PATH, IFN_POINTS_TABLE_PATH
from .tiles import get_tile_url

logger = logging.getLogger(__name__)

LayerSpec = dict[str, Any]

_CONF = ds.IFN_POINTS_JOINED
_F = _CONF["fields"]

#: The parsed filter index. Loaded once per process from a file that never
#: changes. Guarded because several sessions can hit a cold process at once.
_index: list[dict[str, Any]] | None = None
_options: dict[str, Any] | None = None
_index_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# IFN points
# --------------------------------------------------------------------------- #

def filtered_points(
    region: str = "",
    uf: str = "",
    municipality: str = "",
    biome: str = "",
):
    """The IFN collection narrowed by the four selectors. Empty string = no filter."""
    import ee

    fc = ee.FeatureCollection(_CONF["asset"])
    for field, value in (
        (_F["region"], region),
        (_F["uf"], uf),
        (_F["municipality"], municipality),
        (_F["biome"], biome),
    ):
        if value:
            fc = fc.filter(ee.Filter.eq(field, value))
    return fc


def points_by_conglomerado(names: list[str]):
    """The subset of the grid naming these conglomerados.

    Used by the export when the user picked points by hand instead of by filter.
    ``inList`` rather than a chain of ``eq``: a hand-made selection is tens of
    names, which is a small request, and the alternative grows the expression
    tree linearly with the selection.
    """
    import ee

    return ee.FeatureCollection(_CONF["asset"]).filter(
        ee.Filter.inList(_F["conglomerate"], list(names))
    )


def asset_id() -> str:
    """The Earth Engine asset the layer and the exports both read."""
    return _CONF["asset"]


def field_names() -> dict[str, str]:
    """Semantic name → property name. Nothing outside this module should hard-code
    the abbreviated shapefile column names."""
    return dict(_F)


def filter_key(region: str, uf: str, municipality: str, biome: str) -> str:
    """Cache key. Spells the whole combination out — a coarser key serves the
    wrong points from cache, which looks like a data error rather than a bug."""
    return f"ifn:{region}|{uf}|{municipality}|{biome}"


def points_spec(
    region: str = "",
    uf: str = "",
    municipality: str = "",
    biome: str = "",
    opacity: float = 1.0,
    z_index: int = 30,
) -> LayerSpec | None:
    """Tile layer for the filtered IFN points."""
    key = filter_key(region, uf, municipality, biome)

    def build():
        return filtered_points(region, uf, municipality, biome).style(
            **_CONF["style"]
        )

    url = get_tile_url(key, build, {})
    if url is None:
        return None

    return {
        "id": key,
        "url": url,
        "opacity": opacity,
        "attribution": _CONF["attribution"],
        "z_index": z_index,
        # Vector styling is resolution-independent: EE will happily render these
        # dots at any zoom, so there is no native limit to declare.
        "max_native_zoom": 18,
    }


# --------------------------------------------------------------------------- #
# The precomputed index
# --------------------------------------------------------------------------- #

def _load_index() -> list[dict[str, Any]]:
    """Read ``data/ifn_filter_index.csv`` into memory.

    A missing file is not fatal: the map layer still works, since it filters in
    Earth Engine, and the UI degrades to empty dropdowns with an explanation.
    Raising here would take the whole page down over an optional table.
    """
    global _index

    with _index_lock:
        if _index is not None:
            return _index

    rows: list[dict[str, Any]] = []
    try:
        with IFN_FILTER_INDEX_PATH.open(encoding="utf-8", newline="") as handle:
            for raw in csv.DictReader(handle):
                rows.append({
                    "regiao": raw["regiao"],
                    "uf": raw["uf"],
                    "municipio": raw["municipio"],
                    "bioma": raw["bioma"],
                    "pontos": int(raw["pontos"]),
                    "box": (
                        float(raw["lon_min"]), float(raw["lat_min"]),
                        float(raw["lon_max"]), float(raw["lat_max"]),
                    ),
                })
    except FileNotFoundError:
        logger.warning(
            "%s missing — run scripts/join_ifn_biomes.py. Filters will be empty.",
            IFN_FILTER_INDEX_PATH,
        )
    except (OSError, KeyError, ValueError) as exc:
        logger.error("IFN filter index unreadable (%s) — filters disabled", exc)
        rows = []

    with _index_lock:
        _index = rows
    logger.info("IFN filter index: %s groups, %s points", len(rows),
                sum(r["pontos"] for r in rows))
    return rows


def _matching(region: str, uf: str, municipality: str,
              biome: str) -> Iterable[dict[str, Any]]:
    """Index groups selected by the filters. Empty string means "no filter"."""
    for row in _load_index():
        if region and row["regiao"] != region:
            continue
        if uf and row["uf"] != uf:
            continue
        if municipality and row["municipio"] != municipality:
            continue
        if biome and row["bioma"] != biome:
            continue
        yield row


def count(region: str = "", uf: str = "", municipality: str = "",
          biome: str = "") -> int:
    """How many points the current filter selects. A dictionary sum, not a query."""
    return sum(row["pontos"] for row in _matching(region, uf, municipality, biome))


def extent(region: str = "", uf: str = "", municipality: str = "",
           biome: str = "") -> list[list[float]] | None:
    """``[[south, west], [north, east]]`` around the selection, for ``fitBounds``.

    None when nothing is selected, or when no filter is active at all — framing
    the unfiltered grid means framing Brazil, which is where the map already is,
    and yanking the view back there on every "clear filter" is hostile.
    """
    if not (region or uf or municipality or biome):
        return None

    boxes = [row["box"] for row in _matching(region, uf, municipality, biome)]
    if not boxes:
        return None

    west = min(b[0] for b in boxes)
    south = min(b[1] for b in boxes)
    east = max(b[2] for b in boxes)
    north = max(b[3] for b in boxes)

    # A single point has a zero-area box, which fitBounds turns into maximum
    # zoom — a grey square of over-zoomed imagery. Pad it into a ~11 km window.
    if north - south < 0.1:
        south, north = south - 0.05, north + 0.05
    if east - west < 0.1:
        west, east = west - 0.05, east + 0.05
    return [[south, west], [north, east]]


# --------------------------------------------------------------------------- #
# Filter options
# --------------------------------------------------------------------------- #

def options() -> dict[str, Any]:
    """The cascading option lists, derived from the index.

    Derived rather than hard-coded from IBGE's tables so the dropdowns can never
    offer a município with no IFN point in it, and — because biome is a group
    key too — so that picking *Pantanal* narrows the UF list to the four states
    the Pantanal actually reaches.

    Every list is keyed by the filters above it, and a ``""`` key holds the
    unfiltered list, so the UI never has to special-case "nothing selected yet".
    """
    global _options

    with _index_lock:
        if _options is not None:
            return _options

    rows = _load_index()

    regions: set[str] = set()
    biomes_seen: set[str] = set()
    ufs_by: dict[str, set[str]] = {"": set()}
    muns_by: dict[str, set[str]] = {"": set()}
    biomes_by_uf: dict[str, set[str]] = {"": set()}
    region_of_uf: dict[str, str] = {}

    for row in rows:
        region, uf, mun, biome = (row["regiao"], row["uf"], row["municipio"],
                                  row["bioma"])
        if not (region and uf and mun):
            continue
        regions.add(region)
        region_of_uf[uf] = region
        ufs_by[""].add(uf)
        ufs_by.setdefault(f"r:{region}", set()).add(uf)
        muns_by[""].add(mun)
        muns_by.setdefault(f"u:{uf}", set()).add(mun)
        if biome:
            biomes_seen.add(biome)
            ufs_by.setdefault(f"b:{biome}", set()).add(uf)
            muns_by.setdefault(f"u:{uf}|b:{biome}", set()).add(mun)
            biomes_by_uf[""].add(biome)
            biomes_by_uf.setdefault(uf, set()).add(biome)

    def sorted_map(source: dict[str, set[str]]) -> dict[str, list[str]]:
        return {k: sorted(v) for k, v in source.items()}

    resolved = {
        "regions": sorted(regions),
        # Legend order from config, restricted to what actually has points.
        "biomes": [b for b in ds.IBGE_BIOME_DOMAIN["biomes"] if b in biomes_seen],
        "ufs_by": sorted_map(ufs_by),
        "muns_by": sorted_map(muns_by),
        "biomes_by_uf": sorted_map(biomes_by_uf),
        "region_of_uf": region_of_uf,
    }

    with _index_lock:
        _options = resolved
    return resolved


def uf_options(region: str = "", biome: str = "") -> list[str]:
    """UFs available under the current região/bioma choice."""
    opts = options()
    pools = []
    if region:
        pools.append(set(opts["ufs_by"].get(f"r:{region}", [])))
    if biome:
        pools.append(set(opts["ufs_by"].get(f"b:{biome}", [])))
    if not pools:
        return opts["ufs_by"][""]
    return sorted(set.intersection(*pools))


def municipality_options(uf: str = "", biome: str = "") -> list[str]:
    """Municípios available under the current UF/bioma choice.

    Requires a UF: the unfiltered list is 4 100 entries, which is not a dropdown.
    """
    if not uf:
        return []
    opts = options()
    if biome:
        return opts["muns_by"].get(f"u:{uf}|b:{biome}", [])
    return opts["muns_by"].get(f"u:{uf}", [])


def biome_options(uf: str = "") -> list[str]:
    """Biomas present in the current UF — most states have two or three."""
    opts = options()
    if uf:
        available = set(opts["biomes_by_uf"].get(uf, []))
        return [b for b in opts["biomes"] if b in available]
    return opts["biomes"]


def region_of(uf: str) -> str:
    """The região a UF belongs to, so picking a UF can fill the região in."""
    return options()["region_of_uf"].get(uf, "")


# --------------------------------------------------------------------------- #
# The per-point table
# --------------------------------------------------------------------------- #
# Loaded separately from the index because it answers a different question. The
# index says how many conglomerados a filter selects; this says which ones, and
# where. It is what makes the interactive layer possible without a round trip per
# pan: 17 479 rows is a linear scan of a few milliseconds, so no spatial index
# earns its complexity here.

#: Path served by the backend. Relative — the map component resolves it against
#: the backend origin, which differs between the split dev ports and single-port
#: production.
GEOJSON_PATH = "/_ifn_points.geojson"

_points: list[dict[str, Any]] | None = None
_points_lock = threading.Lock()


def _load_points() -> list[dict[str, Any]]:
    """Read ``data/ifn_points_biome.csv`` into memory, once."""
    global _points

    with _points_lock:
        if _points is not None:
            return _points

    rows: list[dict[str, Any]] = []
    try:
        with IFN_POINTS_TABLE_PATH.open(encoding="utf-8", newline="") as handle:
            for raw in csv.DictReader(handle):
                try:
                    lon, lat = float(raw["lon"]), float(raw["lat"])
                except (TypeError, ValueError):
                    continue
                rows.append({
                    "ponto_id": raw["ponto_id"],
                    "conglomerado": raw["conglomerado"],
                    "regiao": raw["regiao"],
                    "uf": raw["uf"],
                    "municipio": raw["municipio"],
                    "bioma": raw["bioma"],
                    "lon": lon,
                    "lat": lat,
                })
    except FileNotFoundError:
        logger.warning(
            "%s missing — run scripts/join_ifn_biomes.py. The conglomerados stay "
            "visible as tiles but cannot be hovered, clicked or exported.",
            IFN_POINTS_TABLE_PATH,
        )
    except (OSError, KeyError) as exc:
        logger.error("IFN point table unreadable (%s)", exc)
        rows = []

    with _points_lock:
        _points = rows
    logger.info("IFN point table: %s conglomerados", len(rows))
    return rows


def _match(row: dict[str, Any], region: str, uf: str, municipality: str,
           biome: str) -> bool:
    return (
        (not region or row["regiao"] == region)
        and (not uf or row["uf"] == uf)
        and (not municipality or row["municipio"] == municipality)
        and (not biome or row["bioma"] == biome)
    )


def selected_points(region: str = "", uf: str = "", municipality: str = "",
                    biome: str = "") -> list[dict[str, Any]]:
    """Every conglomerado the current filter selects, in table order.

    This is the export's definition of "the selection", and it must agree with
    :func:`count` — both read tables written by the same join.
    """
    return [r for r in _load_points() if _match(r, region, uf, municipality, biome)]


def points_named(names: list[str]) -> list[dict[str, Any]]:
    """The rows for a hand-made selection, in table order.

    Table order rather than click order on purpose: an export sorted by UF and
    município is browsable, and the order someone happened to click in carries no
    information anyone can use later.
    """
    wanted = set(names)
    return [r for r in _load_points() if r["conglomerado"] in wanted]


def points_in_bbox(
    west: float, south: float, east: float, north: float,
    region: str = "", uf: str = "", municipality: str = "", biome: str = "",
    limit: int = 1500,
) -> dict[str, Any]:
    """Filtered conglomerados inside a viewport, as GeoJSON.

    Truncation is reported in the collection's ``properties`` rather than
    silently applied: a layer that quietly stops drawing past the 1 500th point
    looks like missing data, and the UI says so instead.
    """
    features = []
    total = 0
    for row in _load_points():
        if not (west <= row["lon"] <= east and south <= row["lat"] <= north):
            continue
        if not _match(row, region, uf, municipality, biome):
            continue
        total += 1
        if len(features) >= limit:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
            "properties": {
                "ponto_id": row["ponto_id"],
                "conglomerado": row["conglomerado"],
                "uf": row["uf"],
                "municipio": row["municipio"],
                "bioma": row["bioma"],
                "lat": row["lat"],
                "lon": row["lon"],
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {"total": total, "returned": len(features),
                       "truncated": total > len(features)},
    }


def vector_spec(
    region: str = "", uf: str = "", municipality: str = "", biome: str = "",
    min_zoom: int = 8, z_index: int = 40,
) -> dict[str, Any]:
    """Spec for the interactive conglomerado layer.

    The tiles below it stay on: they are what makes the national grid visible at
    a glance, and they cost nothing. This layer adds *reachability* — the same
    dots, as real geometry, wherever the user has zoomed in far enough for
    hovering one to be a deliberate act rather than an accident. Its markers are
    drawn slightly larger so they sit exactly over the tiled dots rather than
    beside them.
    """
    return {
        "id": "ifn_interactive",
        "path": GEOJSON_PATH,
        "dynamic": True,
        "min_zoom": min_zoom,
        "z_index": z_index,
        "query": {"region": region, "uf": uf, "municipality": municipality,
                  "biome": biome},
        "point_style": {"radius": 5, "color": "#ffffff", "weight": 1.5,
                        "fillColor": "#e5484d", "fillOpacity": 0.95},
        "hover_style": {"radius": 8, "color": "#ffffff", "weight": 2.5,
                        "fillColor": "#ff8a00", "fillOpacity": 1.0},
        # No tooltip on purpose. It named the same four fields the card in the
        # corner already shows, and it sat directly on top of the buffer preview
        # the hover exists to reveal. The polygons keep theirs — a biome has no
        # card, and its label has nothing to obscure.
        "emit_hover": True,
        "emit_select": True,
    }
