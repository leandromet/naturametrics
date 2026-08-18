#!/usr/bin/env python3
"""Download IFN (Inventário Florestal Nacional) data and build the point catalogue.

Offline preparation tool — the Naturametrics application never calls this at runtime.
It downloads the per-UF files published by the Serviço Florestal Brasileiro on the CKAN
portal at https://dados.florestal.gov.br, then derives a small, deduplicated CSV of
sampling-unit locations that *is* committed to the repo (plus a GeoJSON working copy
under data/cache/ for QGIS).

    python scripts/fetch_ifn.py --list
    python scripts/fetch_ifn.py --uf AC --uf GO
    python scripts/fetch_ifn.py --all --build-catalog

See doc/05-ifn.md for the data model and doc/04-data-sources.md for licensing
(CC-BY, Serviço Florestal Brasileiro — Inventário Florestal Nacional).

Standard library only, so it runs before the venv exists.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

LOG = logging.getLogger("fetch_ifn")

CKAN = "https://dados.florestal.gov.br/api/3/action"
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "ifn"
CACHE_DIR = REPO_ROOT / "data" / "cache"
# D9: the flat CSV is the committed artefact — GeoJSON repeats its keys per feature and
# measured ~2.6x larger, which would break the 2 MB guard at national scale. The GeoJSON
# is still written, to data/cache/, because it is convenient for QGIS and one-off checks.
CATALOG_PATH = REPO_ROOT / "data" / "ifn_points.csv"
CATALOG_GEOJSON_PATH = REPO_ROOT / "data" / "cache" / "ifn_points.geojson"

#: Coordinate precision for the committed catalogue. 5 dp is ~1 m — far finer than a
#: 20 km sampling grid needs, and it meaningfully shrinks the file.
COORD_PRECISION = 5

# Generous bbox around Brazil, used only to reject transposed or corrupt coordinates.
BRAZIL_BBOX = (-75.0, -35.0, -32.0, 6.5)  # min_lon, min_lat, max_lon, max_lat

UF_BY_NAME = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA",
    "ceara": "CE", "distrito federal": "DF", "espirito santo": "ES", "goias": "GO",
    "maranhao": "MA", "mato grosso": "MT", "mato grosso do sul": "MS",
    "minas gerais": "MG", "para": "PA", "paraiba": "PB", "parana": "PR",
    "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ",
    "rio grande do norte": "RN", "rio grande do sul": "RS", "rondonia": "RO",
    "roraima": "RR", "santa catarina": "SC", "sao paulo": "SP", "sergipe": "SE",
    "tocantins": "TO",
}
ALL_UFS = sorted(set(UF_BY_NAME.values()))


@dataclass(frozen=True)
class DatasetSpec:
    """How to find, parse and interpret one IFN dataset."""

    key: str
    slug: str
    label: str
    delimiter: str
    decimal: str
    lat_col: str
    lon_col: str
    ua_col: str
    bioma_col: str
    uf_col: str
    mun_col: str
    date_col: Optional[str] = None
    extra_cols: Tuple[str, ...] = ()


# Verified against the Acre files on 2026-08-18. Note the two dialects differ:
# the biophysical table is comma-delimited with '.' decimals, the socio-environmental
# one is semicolon-delimited with ',' decimals and visibly truncated coordinates.
DATASETS: Dict[str, DatasetSpec] = {
    "ua": DatasetSpec(
        key="ua",
        slug="unidades-amostrais-por-uf-ifn",
        label="Unidades amostrais (biofísico)",
        delimiter=",",
        decimal=".",
        lat_col="lat_pc",
        lon_col="lon_pc",
        ua_col="ua",
        bioma_col="bioma",
        uf_col="uf",
        mun_col="mun",
        date_col="data",
        extra_cols=("impedimento", "Relevo"),
    ),
    "uso": DatasetSpec(
        key="uso",
        slug="ifn-uso-do-solo-e-observacao-do-entorno_disp-set2025",
        label="Uso do solo e observação do entorno (socioambiental)",
        delimiter=";",
        decimal=",",
        lat_col="lat_pc",
        lon_col="long_pc",
        ua_col="ua",
        bioma_col="bioma",
        uf_col="estado",
        mun_col="municipio",
        date_col=None,
        extra_cols=("lote",),
    ),
}


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #

def _get(url: str, *, retries: int = 3, timeout: int = 120) -> bytes:
    """GET with a couple of retries. The portal is occasionally slow, not flaky."""
    last: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "naturametrics-fetch-ifn/1.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            wait = 2 ** attempt
            LOG.warning("  request failed (%s/%s): %s — retrying in %ss",
                        attempt, retries, exc, wait)
            time.sleep(wait)
    raise RuntimeError(f"GET failed after {retries} attempts: {url}") from last


def ckan_package(slug: str) -> dict:
    url = f"{CKAN}/package_show?id={urllib.parse.quote(slug)}"
    payload = json.loads(_get(url).decode("utf-8"))
    if not payload.get("success"):
        raise RuntimeError(f"CKAN returned success=false for {slug}")
    return payload["result"]


# --------------------------------------------------------------------------- #
# Resource → UF resolution
# --------------------------------------------------------------------------- #

def _normalise(text: str) -> str:
    """Lowercase and strip accents, so 'Amapá' matches 'amapa'."""
    import unicodedata
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def resource_uf(resource_name: str) -> Optional[str]:
    """Infer the UF from a resource name.

    Handles both published conventions:
      'Unidades_amostrais_por_UF_IFN_AC.xlsx'            → AC   (2-letter suffix)
      'IFN_Uso-solo-e-Obs-entorno_Acre_disp-set2025.csv' → AC   (state name)
    """
    stem = Path(resource_name).stem
    norm = _normalise(stem)

    # Longest name first, so 'mato grosso do sul' wins over 'mato grosso'.
    for name in sorted(UF_BY_NAME, key=len, reverse=True):
        token = name.replace(" ", "[ _-]*")
        if re.search(rf"(?:^|[_-]){token}(?:$|[_-])", norm):
            return UF_BY_NAME[name]

    # Two-letter code. Scan every candidate, not just the first: names like
    # 'Unidades_amostrais_por_UF_IFN_AC' contain a decoy '_uf_' before the real
    # code. The code is conventionally last, so prefer the rightmost match.
    candidates = [m.group(1).upper()
                  for m in re.finditer(r"(?=(?:^|[_. -])([a-z]{2})(?:$|[_. -]))", norm)]
    for code in reversed(candidates):
        if code in ALL_UFS:
            return code
    return None


def resource_index(spec: DatasetSpec) -> Dict[str, dict]:
    """Map UF → CKAN resource for one dataset, skipping non-data resources."""
    pkg = ckan_package(spec.slug)
    index: Dict[str, dict] = {}
    for res in pkg.get("resources", []):
        name = res.get("name") or ""
        fmt = (res.get("format") or "").upper()
        url = res.get("url") or ""
        if fmt == "PDF" or not url or "/download/" not in url:
            continue  # metadata PDFs and the "all versions" group link
        uf = resource_uf(name)
        if uf:
            index[uf] = res
        else:
            LOG.debug("  could not resolve a UF for resource %r", name)
    return index


def metadata_resources(spec: DatasetSpec) -> List[dict]:
    pkg = ckan_package(spec.slug)
    return [r for r in pkg.get("resources", [])
            if (r.get("format") or "").upper() == "PDF" and r.get("url")]


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #

def download_dataset(spec: DatasetSpec, ufs: Iterable[str], *,
                     force: bool = False) -> Dict[str, Path]:
    """Download the per-UF files for one dataset. Returns UF → local path."""
    dest_dir = RAW_DIR / spec.slug
    dest_dir.mkdir(parents=True, exist_ok=True)

    LOG.info("Resolving resources for %s …", spec.slug)
    index = resource_index(spec)
    LOG.info("  %s per-UF resources published", len(index))

    manifest_path = dest_dir / "_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    out: Dict[str, Path] = {}
    for uf in ufs:
        res = index.get(uf)
        if not res:
            LOG.warning("  %s: no resource published for this UF", uf)
            continue

        url = res["url"]
        # The portal names some resources .xlsx while serving CSV; trust the URL.
        suffix = Path(urllib.parse.urlparse(url).path).suffix or ".csv"
        path = dest_dir / f"{uf}{suffix}"

        if path.exists() and not force:
            LOG.info("  %s: cached (%s)", uf, _human(path.stat().st_size))
            out[uf] = path
            continue

        LOG.info("  %s: downloading …", uf)
        data = _get(url)
        path.write_bytes(data)
        out[uf] = path
        manifest[uf] = {
            "resource_id": res.get("id"),
            "resource_name": res.get("name"),
            "url": url,
            "bytes": len(data),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        LOG.info("     → %s (%s)", path.name, _human(len(data)))

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return out


def download_metadata(spec: DatasetSpec) -> None:
    dest = RAW_DIR / "_metadata"
    dest.mkdir(parents=True, exist_ok=True)
    for res in metadata_resources(spec):
        name = Path(urllib.parse.urlparse(res["url"]).path).name
        path = dest / name
        if path.exists():
            continue
        LOG.info("  metadata: %s", name)
        path.write_bytes(_get(res["url"]))


def _human(n: int) -> str:
    for unit in ("B", "kB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n/1:.1f} {unit}"
        n /= 1024
    return f"{n} B"


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

def _to_float(raw: str, decimal: str) -> Optional[float]:
    raw = (raw or "").strip()
    if not raw or raw.upper() == "NA":
        return None
    if decimal == ",":
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def read_rows(path: Path, spec: DatasetSpec) -> List[dict]:
    """Read one per-UF file. Files are UTF-8 with BOM; encoding is not guaranteed."""
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        LOG.error("  %s: could not decode", path.name)
        return []

    if path.suffix.lower() in (".xlsx", ".xls") and not text.lstrip().startswith(
        ("﻿", '"', spec.delimiter)
    ) and "," not in text[:200] and ";" not in text[:200]:
        LOG.warning("  %s: looks like a real spreadsheet, not CSV — skipping "
                    "(install openpyxl and extend this script if it is needed)",
                    path.name)
        return []

    return list(csv.DictReader(io.StringIO(text), delimiter=spec.delimiter))


def extract_points(rows: List[dict], spec: DatasetSpec) -> Dict[str, dict]:
    """Collapse rows to one record per `ua`.

    The published tables repeat each sampling unit across its subunits/respondents,
    so this deduplicates on `ua`, keeping the first usable coordinates and the
    earliest date.
    """
    points: Dict[str, dict] = {}
    skipped_no_ua = skipped_bad_coord = 0

    for row in rows:
        ua = (row.get(spec.ua_col) or "").strip()
        if not ua or ua.upper() == "NA":
            skipped_no_ua += 1
            continue

        lat = _to_float(row.get(spec.lat_col, ""), spec.decimal)
        lon = _to_float(row.get(spec.lon_col, ""), spec.decimal)

        rec = points.setdefault(ua, {
            "ua": ua,
            "lat": None, "lon": None,
            "bioma": None, "uf": None, "mun": None,
            "date": None,
            "sources": set(),
            "impedimento": None,
            "lote": None,
        })
        rec["sources"].add(spec.key)

        if rec["lat"] is None and lat is not None and lon is not None:
            min_lon, min_lat, max_lon, max_lat = BRAZIL_BBOX
            if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
                rec["lat"], rec["lon"] = lat, lon
            else:
                skipped_bad_coord += 1

        for field_name, col in (("bioma", spec.bioma_col),
                                ("mun", spec.mun_col),
                                ("uf", spec.uf_col)):
            val = (row.get(col) or "").strip()
            if val and val.upper() != "NA" and not rec[field_name]:
                rec[field_name] = val

        if spec.date_col:
            raw_date = (row.get(spec.date_col) or "").strip()
            if raw_date and raw_date.upper() != "NA":
                if rec["date"] is None or raw_date < rec["date"]:
                    rec["date"] = raw_date

        imp = (row.get("impedimento") or "").strip()
        if imp and imp.upper() != "NA":
            rec["impedimento"] = imp

        lote = (row.get("lote") or "").strip()
        if lote and lote.upper() != "NA":
            rec["lote"] = lote

    if skipped_no_ua or skipped_bad_coord:
        LOG.debug("    skipped: %s without ua, %s with out-of-range coords",
                  skipped_no_ua, skipped_bad_coord)
    return points


# --------------------------------------------------------------------------- #
# Catalogue
# --------------------------------------------------------------------------- #

def derive_status(sources: set) -> str:
    """Derive a point status from dataset membership.

    THIS IS DERIVED, NOT OFFICIAL. The SFB does not publish a per-point status field —
    see doc/05-ifn.md §4 and decision D4. Anywhere this reaches a user it must be
    labelled as derived.
    """
    if {"ua", "uso"} <= sources:
        return "medido_completo"
    if "ua" in sources:
        return "medido_biofisico"
    if "uso" in sources:
        return "socioambiental"
    return "desconhecido"


def normalise_uf(value: Optional[str]) -> Optional[str]:
    """'Acre' and 'AC' both arrive; normalise to the two-letter code."""
    if not value:
        return None
    value = value.strip()
    if len(value) == 2 and value.upper() in ALL_UFS:
        return value.upper()
    return UF_BY_NAME.get(_normalise(value))


def build_catalog(ufs: Iterable[str]) -> dict:
    """Merge the downloaded datasets into one deduplicated point catalogue."""
    merged: Dict[str, dict] = {}

    for spec in DATASETS.values():
        dest_dir = RAW_DIR / spec.slug
        if not dest_dir.exists():
            LOG.warning("%s not downloaded — skipping", spec.slug)
            continue
        LOG.info("Parsing %s …", spec.label)
        for uf in ufs:
            matches = list(dest_dir.glob(f"{uf}.*"))
            if not matches:
                continue
            rows = read_rows(matches[0], spec)
            if not rows:
                continue
            points = extract_points(rows, spec)
            LOG.info("  %s: %s rows → %s unidades amostrais", uf, len(rows), len(points))

            for ua, rec in points.items():
                target = merged.setdefault(ua, dict(rec, sources=set()))
                target["sources"] |= rec["sources"]
                for key in ("lat", "lon", "bioma", "uf", "mun", "date",
                            "impedimento", "lote"):
                    if target.get(key) in (None, "") and rec.get(key) not in (None, ""):
                        target[key] = rec[key]

    features = []
    dropped = 0
    for ua, rec in sorted(merged.items()):
        if rec["lat"] is None or rec["lon"] is None:
            dropped += 1
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point",
                         "coordinates": [round(rec["lon"], COORD_PRECISION),
                                         round(rec["lat"], COORD_PRECISION)]},
            "properties": {
                "ua": ua,
                "uf": normalise_uf(rec["uf"]),
                "bioma": rec["bioma"],
                "municipio": rec["mun"],
                "lote": rec["lote"],
                "data": rec["date"],
                "impedimento": rec["impedimento"],
                "status_derivado": derive_status(rec["sources"]),
                "fontes": sorted(rec["sources"]),
            },
        })

    if dropped:
        LOG.warning("%s unidades amostrais had no usable coordinates and were dropped",
                    dropped)

    return {
        "type": "FeatureCollection",
        "name": "ifn_points",
        "metadata": {
            "source": "Serviço Florestal Brasileiro — Inventário Florestal Nacional",
            "portal": "https://dados.florestal.gov.br",
            "license": "CC-BY (Creative Commons Atribuição)",
            "datasets": [s.slug for s in DATASETS.values()],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generator": "scripts/fetch_ifn.py",
            "status_note": (
                "status_derivado is DERIVED from dataset membership, not published by "
                "the SFB — see doc/05-ifn.md section 4"
            ),
            "feature_count": len(features),
        },
        "features": features,
    }


def write_catalog(catalog: dict) -> None:
    """Write the committed CSV catalogue plus a GeoJSON working copy.

    Column order is stable so the committed file diffs readably between regenerations.
    """
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    columns = ["ua", "lon", "lat", "uf", "bioma", "municipio", "lote",
               "data", "impedimento", "status_derivado", "fontes"]

    with CATALOG_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for feat in catalog["features"]:
            props = feat["properties"]
            lon, lat = feat["geometry"]["coordinates"]
            writer.writerow([props["ua"], lon, lat, props["uf"], props["bioma"],
                             props["municipio"], props["lote"], props["data"],
                             props["impedimento"], props["status_derivado"],
                             "|".join(props["fontes"])])

    size = CATALOG_PATH.stat().st_size
    LOG.info("Wrote %s — %s unidades amostrais, %s  (COMMITTED)",
             CATALOG_PATH.relative_to(REPO_ROOT), len(catalog["features"]), _human(size))
    if size > 2 * 1024 * 1024:
        LOG.warning("Catalogue exceeds the 2 MB guard — see decision D9 before committing")

    # Provenance travels beside the CSV, since a bare CSV cannot carry it.
    meta_path = CATALOG_PATH.with_suffix(".meta.json")
    meta_path.write_text(
        json.dumps(catalog["metadata"], indent=2, ensure_ascii=False), encoding="utf-8"
    )
    LOG.info("Wrote %s (provenance, committed)", meta_path.relative_to(REPO_ROOT))

    CATALOG_GEOJSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_GEOJSON_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    LOG.info("Wrote %s (%s, gitignored working copy)",
             CATALOG_GEOJSON_PATH.relative_to(REPO_ROOT),
             _human(CATALOG_GEOJSON_PATH.stat().st_size))


def summarise(catalog: dict) -> None:
    from collections import Counter
    props = [f["properties"] for f in catalog["features"]]
    LOG.info("")
    LOG.info("=== Catalogue summary ===")
    LOG.info("Total unidades amostrais: %s", len(props))
    for label, key in (("By UF", "uf"), ("By bioma", "bioma"),
                       ("By derived status", "status_derivado")):
        counts = Counter(p[key] for p in props)
        LOG.info("%s:", label)
        for value, count in counts.most_common():
            LOG.info("    %-22s %5d", value, count)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def cmd_list() -> None:
    for spec in DATASETS.values():
        LOG.info("")
        LOG.info("=== %s ===", spec.label)
        LOG.info("slug: %s", spec.slug)
        index = resource_index(spec)
        LOG.info("per-UF resources: %s", len(index))
        for uf in sorted(index):
            res = index[uf]
            LOG.info("   %s  %-10s  %s", uf, res.get("format") or "?",
                     res.get("name"))
        missing = sorted(set(ALL_UFS) - set(index))
        if missing:
            LOG.info("   missing UFs: %s", ", ".join(missing))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download IFN data and build the Naturametrics point catalogue.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--list", action="store_true",
                        help="list the datasets and their per-UF resources, download nothing")
    parser.add_argument("--uf", action="append", metavar="UF",
                        help="UF to download (repeatable), e.g. --uf AC --uf GO")
    parser.add_argument("--all", action="store_true", help="all 27 UFs")
    parser.add_argument("--dataset", choices=sorted(DATASETS), action="append",
                        help="limit to one dataset (repeatable); default is all")
    parser.add_argument("--build-catalog", action="store_true",
                        help="build data/ifn_points.csv from what is downloaded")
    parser.add_argument("--catalog-only", action="store_true",
                        help="build the catalogue from existing downloads, fetch nothing")
    parser.add_argument("--metadata", action="store_true",
                        help="also download the metadata PDFs")
    parser.add_argument("--force", action="store_true", help="re-download cached files")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(message)s")

    if args.list:
        cmd_list()
        return 0

    ufs = ALL_UFS if args.all else [u.upper() for u in (args.uf or [])]
    if not ufs and not args.catalog_only:
        parser.error("give --uf UF (repeatable), --all, --list or --catalog-only")
    if args.catalog_only and not ufs:
        ufs = ALL_UFS

    specs = [DATASETS[k] for k in (args.dataset or sorted(DATASETS))]

    if not args.catalog_only:
        for spec in specs:
            LOG.info("")
            LOG.info("=== %s ===", spec.label)
            download_dataset(spec, ufs, force=args.force)
            if args.metadata:
                download_metadata(spec)

    if args.build_catalog or args.catalog_only:
        LOG.info("")
        catalog = build_catalog(ufs)
        if not catalog["features"]:
            LOG.error("No points extracted — nothing written.")
            return 1
        write_catalog(catalog)
        summarise(catalog)

    return 0


if __name__ == "__main__":
    sys.exit(main())
