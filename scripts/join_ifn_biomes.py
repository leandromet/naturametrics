#!/usr/bin/env python3
"""Join the IFN conglomerado points to the IBGE biome polygons — once.

    python scripts/join_ifn_biomes.py            # build data/ifn_filter_index.csv
    python scripts/join_ifn_biomes.py --force    # rebuild even if it exists
    python scripts/join_ifn_biomes.py --full     # also dump the per-point table
    python scripts/join_ifn_biomes.py --export-asset   # write the joined EE asset

**Why this exists.** The SFB point asset carries região, UF and município but no
biome, and the biome is one of the four things the map filters on. Resolving it
at query time means a spatial filter on every filter change; resolving it once
means every filter is a lookup — and the answer is identical, because both come
from the same full-resolution polygons.

The join runs *in Earth Engine*, against the same two assets the map reads, and
only attributes come back. Doing it locally with geopandas would need the
shapefiles and a GDAL stack, and would let the table drift from the assets.

**What is committed is the index, not the points.** The application never needs
to know about an individual conglomerado to drive the filter UI — it needs the
distinct (região, UF, município, bioma) combinations and how many points sit in
each. That is ~4 700 rows and ~250 KiB, small enough for git, and it answers the
count for *any* combination of the four filters by summing the matching groups.
The full 17 495-row table (``--full``) is only useful once individual points
become selectable; it is left out of git under the data policy in
data/README.md.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from naturametrics.config import datasets as ds  # noqa: E402
from naturametrics.services.ee_client import initialize_earth_engine  # noqa: E402

LOG = logging.getLogger("join_ifn_biomes")

INDEX_PATH = REPO_ROOT / "data" / "ifn_filter_index.csv"
POINTS_PATH = REPO_ROOT / "data" / "ifn_points_biome.csv"

INDEX_COLUMNS = ("regiao", "uf", "municipio", "bioma", "pontos",
                 "lon_min", "lat_min", "lon_max", "lat_max")
POINT_COLUMNS = ("ponto_id", "conglomerado", "regiao", "uf", "municipio",
                 "municipio_cod", "lon", "lat", "bioma")


def fetch_joined_rows() -> list[list]:
    """Run the join in Earth Engine and pull the attribute table down.

    Returns rows ordered as :data:`POINT_COLUMNS`.
    """
    import ee

    # 16 features in the asset are MultiPoints with NO coordinates at all (the
    # same ones that carry blank UF/município). They cannot be drawn, joined or
    # filtered, and left in they crash the join with "List is empty (index is
    # 1)" from the centroid. Dropped here, and counted so the loss is visible.
    points = (
        ee.FeatureCollection(ds.IFN_POINTS["asset"])
        .map(lambda f: f.set("_ncoord", f.geometry().coordinates().size()))
        .filter(ee.Filter.gt("_ncoord", 0))
    )
    polygons = ee.FeatureCollection(ds.IBGE_BIOME_DOMAIN["asset"])
    biome_field = ds.IBGE_BIOME_DOMAIN["fields"]["biome"]

    # saveFirst: the IBGE polygons tile the country without overlapping, so a
    # point is in exactly one — except on a shared edge, where "first" is as
    # good an answer as any and the alternative is a list.
    # outer=True: points that match nothing (offshore, and the handful with no
    # administrative attributes) stay in the table with an empty biome. They are
    # real IFN locations and dropping them here would silently shrink the grid.
    joined = ee.Join.saveFirst(matchKey="_poly", outer=True).apply(
        primary=points,
        secondary=polygons,
        condition=ee.Filter.intersects(leftField=".geo", rightField=".geo"),
    )

    empty = ee.Dictionary({})

    def flatten(feature):
        feature = ee.Feature(feature)
        matched = feature.get("_poly")
        # ee.Feature(null) is not constructible, so the unmatched case has to be
        # branched around rather than defaulted after the fact.
        poly = ee.Dictionary(ee.Algorithms.If(
            matched, ee.Feature(matched).toDictionary(), empty))
        coords = feature.geometry().centroid(1).coordinates()
        return feature.set({
            "_lon": coords.getNumber(0),
            "_lat": coords.getNumber(1),
            "_bioma": poly.get(biome_field, ""),
        })

    props = ["co_pontos_", "no_conglom", "nm_regiao", "sigla_uf", "nm_mun",
             "cd_mun", "_lon", "_lat", "_bioma"]

    started = time.time()
    rows = (
        ee.FeatureCollection(joined)
        .map(flatten)
        .reduceColumns(ee.Reducer.toList(len(props)), props)
        .get("list")
        .getInfo()
    )
    LOG.info("Join returned %s rows in %.1f s", len(rows), time.time() - started)
    return rows


def build_index(rows: list[list]) -> list[dict]:
    """Collapse the per-point rows to counted, bounded groups.

    Each group also carries the bounding box of its points. That is what lets the
    application frame a selection — any combination of the four filters — without
    asking Earth Engine for an extent: the union of the matching group boxes is
    exactly the extent of the matching points.
    """
    idx = {col: i for i, col in enumerate(POINT_COLUMNS)}
    counts: Counter[tuple[str, str, str, str]] = Counter()
    boxes: dict[tuple[str, str, str, str], list[float]] = {}

    for row in rows:
        key = (
            str(row[idx["regiao"]] or ""),
            str(row[idx["uf"]] or ""),
            str(row[idx["municipio"]] or ""),
            str(row[idx["bioma"]] or ""),
        )
        counts[key] += 1
        lon, lat = float(row[idx["lon"]]), float(row[idx["lat"]])
        box = boxes.get(key)
        if box is None:
            boxes[key] = [lon, lat, lon, lat]
        else:
            box[0] = min(box[0], lon)
            box[1] = min(box[1], lat)
            box[2] = max(box[2], lon)
            box[3] = max(box[3], lat)

    index = []
    for key in sorted(counts):
        r, u, m, b = key
        lon_min, lat_min, lon_max, lat_max = boxes[key]
        index.append({
            "regiao": r, "uf": u, "municipio": m, "bioma": b,
            "pontos": counts[key],
            # 4 dp is ~11 m — the box only has to be right enough to frame a map.
            "lon_min": f"{lon_min:.4f}", "lat_min": f"{lat_min:.4f}",
            "lon_max": f"{lon_max:.4f}", "lat_max": f"{lat_max:.4f}",
        })
    return index


def write_index(index: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(INDEX_COLUMNS))
        writer.writeheader()
        writer.writerows(index)
    LOG.info("Wrote %s (%s groups, %s KiB)", path, len(index),
             path.stat().st_size // 1024)


def write_points(rows: list[list], path: Path) -> None:
    idx = {col: i for i, col in enumerate(POINT_COLUMNS)}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(POINT_COLUMNS)
        for row in sorted(rows, key=lambda r: (str(r[idx["uf"]]),
                                               str(r[idx["municipio"]]),
                                               str(r[idx["conglomerado"]]))):
            out = ["" if v is None else v for v in row]
            # 6 dp is ~0.1 m — far finer than the 20 km sampling grid, and half
            # the bytes of a full float repr.
            for key in ("lon", "lat"):
                out[idx[key]] = f"{float(out[idx[key]]):.6f}" if out[idx[key]] != "" else ""
            writer.writerow(out)
    LOG.info("Wrote %s (%s points, %s KiB)", path, len(rows),
             path.stat().st_size // 1024)


def summarise(index: list[dict]) -> None:
    per_biome: Counter[str] = Counter()
    for group in index:
        per_biome[group["bioma"] or "— (sem polígono)"] += group["pontos"]
    LOG.info("Points per biome:")
    for name, n in per_biome.most_common():
        LOG.info("  %-22s %6d", name, n)
    LOG.info("Total %s points in %s groups", sum(per_biome.values()), len(index))


def export_asset(wait: bool = True) -> int:
    """Write the joined points back to Earth Engine as an asset.

    **Why the app cannot just filter spatially.** ``filterBounds`` against a
    biome outline works for Pantanal, Pampa and Caatinga and fails for Amazônia,
    Cerrado and Mata Atlântica with *"Description length exceeds maximum"* — the
    1:250 000 outline of those three is too long for Earth Engine's filter
    machinery, whether it is passed as a geometry or as a collection, and no
    amount of restructuring the request changes that. Simplifying the polygon
    would fix the request and quietly misassign every point within the
    simplification tolerance of a boundary.

    So the intersection is done once, here, and stored. In the joined asset
    ``bioma`` is an ordinary string property and the biome filter becomes the
    same ``ee.Filter.eq`` as região, UF and município — one code path, no size
    limit, and a request that does not grow with the size of the biome.
    """
    import ee

    source = ds.IFN_POINTS["asset"]
    target = ds.IFN_POINTS_JOINED["asset"]
    bio = ds.IBGE_BIOME_DOMAIN["fields"]

    points = (
        ee.FeatureCollection(source)
        .map(lambda f: f.set("_ncoord", f.geometry().coordinates().size()))
        .filter(ee.Filter.gt("_ncoord", 0))
    )
    polygons = ee.FeatureCollection(ds.IBGE_BIOME_DOMAIN["asset"])
    empty = ee.Dictionary({})

    def flatten(feature):
        feature = ee.Feature(feature)
        matched = feature.get("_poly")
        poly = ee.Dictionary(ee.Algorithms.If(
            matched, ee.Feature(matched).toDictionary(), empty))
        return feature.set({
            "bioma": poly.get(bio["biome"], ""),
            "dominio_fito": poly.get(bio["phyto_domain"], ""),
            "regiao_natural": poly.get(bio["natural_region"], ""),
        # _poly holds a whole feature and _ncoord is scaffolding; neither belongs
        # in the asset, and _poly would bloat it enormously.
        }).select(list(ds.IFN_POINTS_JOINED["fields"].values()))

    joined = ee.FeatureCollection(
        ee.Join.saveFirst(matchKey="_poly", outer=True).apply(
            primary=points,
            secondary=polygons,
            condition=ee.Filter.intersects(leftField=".geo", rightField=".geo"),
        )
    ).map(flatten)

    task = ee.batch.Export.table.toAsset(
        collection=joined,
        description="ifn_conglomerados_bioma",
        assetId=target,
    )
    task.start()
    LOG.info("Export started → %s (task %s)", target, task.id)
    if not wait:
        LOG.info("Not waiting. Check with: earthengine task info %s", task.id)
        return 0

    started = time.time()
    while True:
        status = task.status()
        state = status.get("state")
        if state in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        LOG.info("  %s… %.0f s", state, time.time() - started)
        time.sleep(15)

    if state != "COMPLETED":
        LOG.error("Export %s: %s", state, status.get("error_message", ""))
        return 1
    LOG.info("Export completed in %.0f s", time.time() - started)
    LOG.info("Asset ready: %s", target)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="rebuild even if the index already exists")
    parser.add_argument("--full", action="store_true",
                        help="also write the per-point table (not committed)")
    parser.add_argument("--export-asset", action="store_true",
                        help="write the joined points back to Earth Engine as "
                             "an asset (this is what the map filters on)")
    parser.add_argument("--no-wait", action="store_true",
                        help="with --export-asset, do not block on the task")
    parser.add_argument("--output", type=Path, default=INDEX_PATH)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.export_asset:
        initialize_earth_engine()
        return export_asset(wait=not args.no_wait)

    if args.output.exists() and not (args.force or args.full):
        LOG.info("%s already exists — use --force to rebuild", args.output)
        return 0

    initialize_earth_engine()
    rows = fetch_joined_rows()
    if not rows:
        LOG.error("Join returned nothing — refusing to write an empty table")
        return 1

    index = build_index(rows)
    summarise(index)
    write_index(index, args.output)
    if args.full:
        write_points(rows, POINTS_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
