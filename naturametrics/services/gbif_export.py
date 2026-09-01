"""The GBIF species tab as a spreadsheet.

Same shape as every other workbook this app produces (services/exports.py): a
``metadados`` tab first, then the data. Here the data is one tab per buffer
radius, which is the on-screen layout — one card per radius — carried straight
across, so somebody who has looked at the tab already knows how to read the
file.

Written here rather than in services/exports.py, which is 1 422 lines and
entirely about Earth Engine: nothing in this module touches EE, there is no
provenance chain to record because there was no computation to record — the
numbers are counts returned by a third party — and the caveats that matter are
GBIF's own, not ours. It reuses that module's ``ods`` writer and its citation
constants, which is the part worth sharing.

**Nothing here re-queries GBIF.** The workbook is built from the rows already in
state, so the file and the screen always agree. That matters more than
completeness would: a re-query would silently apply whatever filters are set at
the moment of the click rather than the ones that produced the results being
looked at.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Iterable, Sequence

from ..config import gbif as gc
from ..config.citation import CITATION_TEXT, DATA_SOURCES
from ..config.settings import (
    GBIF_EXPORT_SPECIES_LIMIT,
    GBIF_FACET_LIMIT,
    GBIF_SPECIES_TABLE_LIMIT,
)
from . import ods

logger = logging.getLogger(__name__)

MIMETYPE = ods.MIMETYPE

#: Columns of a per-radius tab, and of the flat CSV.
SPECIES_COLUMNS = ["raio_km", "especie", "registros", "pct_do_raio"]
CSV_COLUMNS = SPECIES_COLUMNS


def _now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _radius_slug(radius_km: float) -> str:
    """``0.5 -> "00_5km"``, ``10.0 -> "10km"`` — a tab name that sorts correctly.

    Zero-padded because a spreadsheet's tab bar is ordered as written and
    ``10km`` would otherwise sit between ``1km`` and ``2km``; the decimal point
    is replaced because ODF forbids nothing here but LibreOffice's own name
    validation is inconsistent about it across versions.
    """
    if float(radius_km).is_integer():
        return f"{int(radius_km):02d}km"
    return f"{radius_km:04.1f}km".replace(".", "_")


def _species_rows(row: Any) -> list[list[Any]]:
    """One radius' species table, as spreadsheet rows.

    ``pct_do_raio`` is each species' share of that radius' own record total —
    the one derived number worth precomputing, because it is what makes two
    radii comparable when their totals differ by two orders of magnitude, and
    because a reader who wants it in a spreadsheet formula needs the divisor,
    which is on a different tab.
    """
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
    """The tab the workbook opens with.

    Carries the three things a reader needs six months later and cannot
    reconstruct from the data tabs: where the point was, what was filtered, and
    which of these numbers are floors rather than counts.
    """
    out: list[list[Any]] = [
        ["Naturametrics — espécies registradas (GBIF)", ""],
        ["gerado em (UTC)", _now_iso()],
        ["endereço", "https://www.gbif.org"],
        ["", ""],
        ["PONTO DE ESTUDO", ""],
    ]
    out.extend([list(c) for c in context])

    out.append(["", ""])
    out.append(["FILTROS APLICADOS", "os mesmos da busca na barra lateral"])
    if filters:
        out.extend([list(f) for f in filters])
    else:
        out.append(["  (nenhum)", "todos os registros do Brasil no raio"])

    out.append(["", ""])
    out.append(["RESUMO POR RAIO", ""])
    out.append(["  raio (km)", "registros | espécies distintas"])
    for row in rows:
        richness = int(getattr(row, "richness", 0) or 0)
        capped = richness >= GBIF_FACET_LIMIT
        listed = len(getattr(row, "species", []) or [])
        out.append([
            f"  {float(getattr(row, 'radius_km', 0)):g} km",
            f"{int(getattr(row, 'total', 0) or 0)} registros | "
            f"{richness}{'+' if capped else ''} espécies"
            f" | {listed} listadas nesta planilha",
        ])
        if getattr(row, "error", ""):
            out.append(["    falha", str(row.error)])

    out.append(["", ""])
    out.append(["COMO LER ESTES NÚMEROS", ""])
    out.append([
        "  buffers",
        "Discos CUMULATIVOS a partir do ponto: o raio de 10 km inclui tudo o "
        "que está no de 5 km. Não são anéis, e as abas não se somam.",
    ])
    out.append([
        "  espécies distintas",
        f"Conta os nomes científicos distintos devolvidos pelo GBIF. O teto da "
        f"consulta é {GBIF_FACET_LIMIT}; um raio que o alcança aparece como "
        f"«{GBIF_FACET_LIMIT}+» e o valor é um PISO, não uma contagem.",
    ])
    out.append([
        "  linhas por aba",
        f"Cada aba traz as {GBIF_EXPORT_SPECIES_LIMIT} espécies mais "
        f"registradas do seu raio (a tela mostra as {GBIF_SPECIES_TABLE_LIMIT} "
        f"primeiras). Um raio com mais espécies do que isso está truncado — "
        f"compare «espécies distintas» com «listadas» no resumo acima.",
    ])
    out.append([
        "  nomes",
        "O nome é o scientificName interpretado pelo GBIF. Um registro "
        "determinado só até família ou gênero aparece com esse nome de família "
        "ou gênero, e não como espécie.",
    ])
    out.append([
        "  esforço amostral",
        "Contagem de REGISTROS, não de indivíduos nem de abundância. Reflete "
        "onde alguém coletou ou observou, não onde a espécie ocorre — áreas "
        "perto de instituições de pesquisa são fortemente sobre-representadas.",
    ])

    out.append(["", ""])
    out.append(["LICENÇA — ATENÇÃO", ""])
    out.append([
        "  uso comercial",
        "O GBIF agrega conjuntos com licenças diferentes (CC0, CC-BY e "
        "CC-BY-NC). Esta consulta NÃO exclui os CC-BY-NC, que vedam uso "
        "comercial. Verifique a licença de cada conjunto antes de tal uso.",
    ])
    out.append([
        "  citação",
        f"Cite a consulta e a data de acesso: «GBIF.org ({_now_iso()[:10]}) "
        f"GBIF Occurrence Search» e credite os conjuntos de origem.",
    ])

    out.append(["", ""])
    out.append(["COMO CITAR ESTE APLICATIVO", ""])
    out.append(["citação", CITATION_TEXT])
    out.append(["", ""])
    out.append(["ATRIBUIÇÕES OBRIGATÓRIAS", "cite as bases usadas ao publicar"])
    for name, detail, url in DATA_SOURCES:
        out.append([name, f"{detail} {url}"])

    return ods.Sheet("metadados", ["campo", "valor"], out)


def build_ods(rows: Sequence[Any], context: Sequence[Sequence[Any]],
              filters: Sequence[Sequence[Any]]) -> tuple[bytes, str]:
    """The workbook: ``metadados`` plus one tab per radius."""
    sheets = [_metadata_sheet(rows, context, filters)]
    for row in rows:
        radius = float(getattr(row, "radius_km", 0.0))
        sheets.append(ods.Sheet(
            f"especies_{_radius_slug(radius)}",
            SPECIES_COLUMNS,
            _species_rows(row),
        ))
    data = ods.write(sheets)
    return data, "naturametrics_especies_gbif.ods"


def build_csv(rows: Iterable[Any]) -> tuple[bytes, str]:
    """Every radius in one flat table.

    The counterpart to the workbook, for a script rather than a reader: same
    columns as a radius tab, with ``raio_km`` distinguishing them, and none of
    the metadata. The caveats in the workbook's first tab apply to this file
    too — which is exactly why it is offered alongside the ODS rather than
    instead of it.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerows(_species_rows(row))
    return buffer.getvalue().encode("utf-8"), "naturametrics_especies_gbif.csv"


__all__ = ["MIMETYPE", "build_ods", "build_csv", "SPECIES_COLUMNS", "CSV_COLUMNS"]
