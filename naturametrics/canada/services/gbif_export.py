"""The GBIF species tab as a spreadsheet — the Canada page.

Same shape as the Brazil page's ``services/gbif_export.py`` (one metadata tab,
then one tab per buffer radius) — see that file for the full rationale. Not
reused directly, unlike gbif_taxa.py/gbif_buffers.py: the Brazil version's
metadata sheet is written entirely in Portuguese, including a line that names
Brazil by name ("todos os registros do Brasil no raio"), matching the Brazil
export convention (naturametrics/services/exports.py is Portuguese too). The
Canada page's own workbook (canada/services/exports.py) is English throughout,
so this file follows that page's convention rather than the Brazil one.

Nothing here re-queries GBIF — same reasoning as the Brazil file: the workbook
is built from the rows already in state, so the file and the screen agree.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Iterable, Sequence

from ...config.settings import (
    GBIF_EXPORT_SPECIES_LIMIT,
    GBIF_FACET_LIMIT,
    GBIF_SPECIES_TABLE_LIMIT,
)
from ...services import ods

logger = logging.getLogger(__name__)

MIMETYPE = ods.MIMETYPE

SPECIES_COLUMNS = ["radius_km", "species", "records", "pct_of_radius"]
CSV_COLUMNS = SPECIES_COLUMNS

#: Page-scoped, like canada/services/exports.py::DATA_SOURCES — only the
#: source this workbook actually draws on, not the whole app's citation list.
DATA_SOURCES = [
    ("GBIF — Species occurrence records",
     "GBIF.org — Global Biodiversity Information Facility. Records queried "
     "live through the occurrence API, restricted to Canada. When publishing "
     "results, cite the query and access date in GBIF's recommended form "
     "(“GBIF.org (dd mmm yyyy) GBIF Occurrence Search”) and credit "
     "the constituent datasets, which carry their own licences (CC0, CC-BY "
     "and CC-BY-NC). This query does NOT exclude CC-BY-NC data, which "
     "prohibits commercial use. GBIF's Canadian node is CBIF (Canada "
     "Biodiversity Information Facility).",
     "https://www.gbif.org"),
]


def _now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _radius_slug(radius_km: float) -> str:
    """Same zero-padded, decimal-free tab-naming scheme as the Brazil file —
    see that module's comment on why (tab-bar sort order, LibreOffice naming)."""
    if float(radius_km).is_integer():
        return f"{int(radius_km):02d}km"
    return f"{radius_km:04.1f}km".replace(".", "_")


def _species_rows(row: Any) -> list[list[Any]]:
    total = getattr(row, "total", 0) or 0
    out = []
    for sp in getattr(row, "species", []) or []:
        count = int(getattr(sp, "count", 0) or 0)
        out.append([
            float(getattr(row, "radius_km", 0.0)),
            str(getattr(sp, "name", "")),
            count,
            round(count / total * 100.0, 4) if total else 0.0,
        ])
    return out


def _metadata_sheet(rows: Sequence[Any], context: Sequence[Sequence[Any]],
                    filters: Sequence[Sequence[Any]]) -> ods.Sheet:
    out: list[list[Any]] = [
        ["Naturametrics Canada — species recorded (GBIF)", ""],
        ["generated_utc", _now_iso()],
        ["source", "https://www.gbif.org"],
        ["", ""],
        ["STUDY POINT", ""],
    ]
    out.extend([list(c) for c in context])

    out.append(["", ""])
    out.append(["FILTERS APPLIED", "same as the sidebar search"])
    if filters:
        out.extend([list(f) for f in filters])
    else:
        out.append(["  (none)", "every Canadian record in the radius"])

    out.append(["", ""])
    out.append(["SUMMARY BY RADIUS", ""])
    out.append(["  radius (km)", "records | distinct species"])
    for row in rows:
        richness = int(getattr(row, "richness", 0) or 0)
        capped = richness >= GBIF_FACET_LIMIT
        listed = len(getattr(row, "species", []) or [])
        out.append([
            f"  {float(getattr(row, 'radius_km', 0)):g} km",
            f"{int(getattr(row, 'total', 0) or 0)} records | "
            f"{richness}{'+' if capped else ''} species"
            f" | {listed} listed in this sheet",
        ])
        if getattr(row, "error", ""):
            out.append(["    failed", str(row.error)])

    out.append(["", ""])
    out.append(["HOW TO READ THESE NUMBERS", ""])
    out.append([
        "  buffers",
        "Cumulative discs from the point: the 10 km radius includes "
        "everything in the 5 km one. They are not rings, and the tabs do "
        "not add up.",
    ])
    out.append([
        "  distinct species",
        f"Counts distinct scientific names returned by GBIF. The query is "
        f"capped at {GBIF_FACET_LIMIT}; a radius that reaches it shows as "
        f"«{GBIF_FACET_LIMIT}+» and the value is a FLOOR, not a count.",
    ])
    out.append([
        "  rows per tab",
        f"Each tab carries the {GBIF_EXPORT_SPECIES_LIMIT} most-recorded "
        f"species for its radius (the screen shows the first "
        f"{GBIF_SPECIES_TABLE_LIMIT}). A radius with more species than that "
        f"is truncated — compare «distinct species» with «listed» "
        f"above.",
    ])
    out.append([
        "  names",
        "The name is the scientificName GBIF interpreted. A record "
        "determined only to family or genus appears under that family or "
        "genus name, not as a species.",
    ])
    out.append([
        "  sampling effort",
        "Counts RECORDS, not individuals or abundance. Reflects where "
        "someone collected or observed, not where the species occurs — "
        "areas near research institutions are heavily over-represented.",
    ])

    out.append(["", ""])
    out.append(["LICENCE — NOTE", ""])
    out.append([
        "  commercial use",
        "GBIF aggregates datasets under different licences (CC0, CC-BY and "
        "CC-BY-NC). This query does NOT exclude CC-BY-NC ones, which "
        "prohibit commercial use. Check each dataset's licence before such "
        "use.",
    ])
    out.append([
        "  citation",
        f"Cite the query and the access date: «GBIF.org ({_now_iso()[:10]}) "
        f"GBIF Occurrence Search» and credit the source datasets.",
    ])

    out.append(["", ""])
    out.append(["ATTRIBUTIONS", "cite the sources used when publishing"])
    for name, detail, url in DATA_SOURCES:
        out.append([name, f"{detail} {url}"])

    return ods.Sheet("metadata", ["field", "value"], out)


def build_ods(rows: Sequence[Any], context: Sequence[Sequence[Any]],
              filters: Sequence[Sequence[Any]]) -> tuple[bytes, str]:
    """The workbook: ``metadata`` plus one tab per radius."""
    sheets = [_metadata_sheet(rows, context, filters)]
    for row in rows:
        radius = float(getattr(row, "radius_km", 0.0))
        sheets.append(ods.Sheet(
            f"species_{_radius_slug(radius)}",
            SPECIES_COLUMNS,
            _species_rows(row),
        ))
    data = ods.write(sheets)
    return data, "naturametrics_canada_species_gbif.ods"


def build_csv(rows: Iterable[Any]) -> tuple[bytes, str]:
    """Every radius in one flat table — the Brazil file's ``build_csv``,
    ported. Same caveats as the workbook apply, which is why it ships beside
    it rather than instead of it."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerows(_species_rows(row))
    return buffer.getvalue().encode("utf-8"), "naturametrics_canada_species_gbif.csv"


__all__ = ["MIMETYPE", "build_ods", "build_csv", "SPECIES_COLUMNS", "CSV_COLUMNS"]
