"""Building the downloadable spreadsheets.

Two exports, deliberately separate because they answer different questions:

* **the study point** — everything computed about the one location on screen:
  its own pixel's 40-year class series, plus the land-cover history of each of
  the four buffers. Small, always available once an analysis has run.
* **the conglomerado selection** — the same measurements across every IFN point
  the current filters select. The single-pixel half is cheap at any size; the
  buffer half is not, and its ceiling depends on which radii are asked for
  (see :func:`max_points_for`).

Both are **one ODS file with a tab per table**, not a ZIP of CSVs: a spreadsheet
is already a compressed container, it opens on a double-click, and it keeps the
metadata attached to the data instead of in a sibling file that gets separated
from it the first time someone emails one sheet to a colleague.

Constraint **C6** (doc/01-premises.md) is enforced structurally here: every
workbook starts with a ``metadados`` tab, and the functions that build one take
the :class:`~naturametrics.services.provenance.Provenance` records as required
arguments. There is no code path that writes a sheet of numbers without one.
"""

from __future__ import annotations

import dataclasses
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Sequence

import pandas as pd

from ..config import mapbiomas as mb
from ..config.citation import APP_URL, CITATION_TEXT, DATA_SOURCES
from ..config.settings import (
    BUFFER_MODE_DEFAULT, BUFFER_RADII_KM, EXPORT_MAX_TOTAL_ROWS,
    EXPORT_ODS_ROWS_PER_SHEET, EXPORT_POINT_TIMEOUT_S, EXPORT_ROWS_PER_POINT,
    EXPORT_SECONDS_PER_POINT,
)
from . import ifn, ods
from .geo import Point, point
from .mapbiomas_history import land_cover_history, point_pixel_series
from .provenance import Provenance

logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"

#: Repeated verbatim wherever a single-pixel table appears. The measurement is
#: legitimate and the caveat is not optional — see doc/11 §2.
PIXEL_CAVEAT = (
    "Valores de UM pixel de 30 m. Um único pixel é ruidoso: um ano mal "
    "classificado aparece como uma transição que não existiu. Para tendência, "
    "use as abas de buffer, que agregam milhares de pixels."
)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# The metadata tab
# --------------------------------------------------------------------------- #

def _provenance_rows(prov: Provenance) -> list[list[Any]]:
    """One provenance record flattened into key/value rows."""
    d = prov.to_dict()
    rows: list[list[Any]] = [
        [f"— {d['name']} —", ""],
        ["  conjunto de dados", d["dataset_id"]],
        ["  bandas", f"{len(d['bands'])} ({d['bands'][0]}…{d['bands'][-1]})"
                     if d["bands"] else ""],
        ["  escala (m)", d["scale_m"]],
        ["  redutor", d["reducer"]],
        ["  base de área", d["pixel_area_basis"]],
        ["  tileScale", d["tile_scale"]],
        ["  maxPixels", d["max_pixels"]],
        ["  calculado em", d["computed_at"]],
        ["  resultado degradado", bool(d["degraded"])],
    ]
    for note in d.get("notes") or []:
        rows.append(["  aviso", note])
    for key, value in (d.get("extra") or {}).items():
        rows.append([f"  {key}", str(value)])
    return rows


def _metadata_sheet(title: str, context: Sequence[Sequence[Any]],
                    provenances: Iterable[Provenance]) -> ods.Sheet:
    """The tab every workbook opens with.

    Prose plus key/value pairs rather than raw JSON: this is the sheet somebody
    reads six months later to decide whether they can defend the numbers beside
    it, and JSON in a spreadsheet cell is not readable.
    """
    rows: list[list[Any]] = [
        ["Naturametrics — " + title, ""],
        ["gerado em (UTC)", _now_iso()],
        ["versão do aplicativo", APP_VERSION],
        ["endereço", APP_URL],
        ["", ""],
    ]
    rows.extend([list(r) for r in context])
    rows.append(["", ""])
    rows.append(["PROVENIÊNCIA", "cada consulta ao Earth Engine que gerou estes dados"])
    for prov in provenances:
        rows.extend(_provenance_rows(prov))
        rows.append(["", ""])

    rows.append(["COMO CITAR", ""])
    rows.append(["citação", CITATION_TEXT])
    rows.append(["", ""])
    rows.append(["ATRIBUIÇÕES OBRIGATÓRIAS", "cite as bases usadas ao publicar"])
    for name, detail, url in DATA_SOURCES:
        rows.append([name, f"{detail} {url}"])
    return ods.Sheet("metadados", ["campo", "valor"], rows)


def _classes_sheet() -> ods.Sheet:
    """The MapBiomas code → name → colour dictionary.

    Without it every other sheet is a column of integers, and the reader has to
    go and find the legend elsewhere.
    """
    rows = [[cid, mb.label(cid, "pt"), mb.label(cid, "en"), mb.color(cid)]
            for cid in sorted(mb.MAPBIOMAS_LABELS_PT)]
    return ods.Sheet("classes_mapbiomas",
                     ["class_id", "classe_pt", "class_en", "cor_hex"], rows)


# --------------------------------------------------------------------------- #
# Study point
# --------------------------------------------------------------------------- #

def _with_shares(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``area_pct`` within each (radius, year). The chart shows shares, so
    an export without them forces the reader to recompute what they just saw."""
    if df.empty:
        return df
    out = df.copy()
    totals = out.groupby(["radius_km", "year"])["area_ha"].transform("sum")
    out["area_pct"] = (out["area_ha"] / totals * 100.0).fillna(0.0).round(4)
    out["area_ha"] = out["area_ha"].round(4)
    return out


def _buffer_summary(df: pd.DataFrame) -> pd.DataFrame:
    """First year, last year and net change per class per buffer."""
    if df.empty:
        return pd.DataFrame(columns=["radius_km", "class_id", "classe_pt",
                                     "area_primeiro_ano_ha", "area_ultimo_ano_ha",
                                     "variacao_ha", "variacao_pct"])
    first_year, last_year = df["year"].min(), df["year"].max()
    first = (df[df["year"] == first_year]
             .set_index(["radius_km", "class_id"])["area_ha"])
    last = (df[df["year"] == last_year]
            .set_index(["radius_km", "class_id"])["area_ha"])
    joined = pd.concat([first.rename("primeiro"), last.rename("ultimo")], axis=1)
    joined = joined.fillna(0.0).reset_index()
    joined["classe_pt"] = joined["class_id"].map(lambda c: mb.label(int(c), "pt"))
    joined["variacao_ha"] = (joined["ultimo"] - joined["primeiro"]).round(4)
    # `.where` rather than `.replace(0, pd.NA)`: pandas 3 gives the latter a
    # masked dtype whose NAType then refuses to cast back to float. A class that
    # was absent in the first year has no meaningful percentage change, and NaN
    # is the honest value for that — an empty cell, not a zero.
    baseline = joined["primeiro"].where(joined["primeiro"] != 0.0)
    joined["variacao_pct"] = (
        (joined["ultimo"] - joined["primeiro"]) / baseline * 100.0
    ).round(2)
    joined = joined.rename(columns={"primeiro": "area_primeiro_ano_ha",
                                    "ultimo": "area_ultimo_ano_ha"})
    joined["area_primeiro_ano_ha"] = joined["area_primeiro_ano_ha"].round(4)
    joined["area_ultimo_ano_ha"] = joined["area_ultimo_ano_ha"].round(4)
    return joined.sort_values(["radius_km", "variacao_ha"],
                              ascending=[True, False])[
        ["radius_km", "class_id", "classe_pt", "area_primeiro_ano_ha",
         "area_ultimo_ano_ha", "variacao_ha", "variacao_pct"]
    ]


def study_point_workbook(
    p: Point,
    history: pd.DataFrame,
    history_prov: Provenance,
    pixel: pd.DataFrame,
    pixel_prov: Provenance,
    identity: dict[str, Any] | None = None,
) -> tuple[bytes, str]:
    """One spreadsheet for the location currently under analysis.

    Returns ``(bytes, filename)``. Nothing is recomputed here — the history is
    the frame already on screen, so the file and the chart cannot disagree
    (doc/11 §5).
    """
    identity = identity or {}
    history = _with_shares(history)

    context: list[list[Any]] = [
        ["ESCOPO", "ponto de estudo"],
        ["latitude", round(p.lat, 6)],
        ["longitude", round(p.lon, 6)],
        ["origem do ponto", identity.get("source", "clique no mapa")],
    ]
    if identity.get("conglomerado"):
        context += [
            ["conglomerado (IFN)", identity.get("conglomerado", "")],
            ["município", identity.get("municipio", "")],
            ["UF", identity.get("uf", "")],
            ["bioma", identity.get("bioma", "")],
        ]
    context += [
        ["raios dos buffers (km)", ", ".join(f"{r:g}" for r in BUFFER_RADII_KM)],
        ["modo dos buffers", BUFFER_MODE_DEFAULT],
        ["anos", f"{mb.MAPBIOMAS_YEAR_START}–{mb.MAPBIOMAS_YEAR_END}"],
        ["", ""],
        ["AVISO — abas de pixel", PIXEL_CAVEAT],
    ]

    sheets = [
        _metadata_sheet("ponto de estudo", context, [pixel_prov, history_prov]),
        ods.sheet_from_dataframe(
            "ponto_pixel", pixel, ["year", "class_id", "class_pt", "class_en"]),
    ]

    for radius in sorted(BUFFER_RADII_KM):
        sub = history[history["radius_km"] == radius] if not history.empty else history
        sheets.append(ods.sheet_from_dataframe(
            f"buffer_{int(radius):02d}km", sub,
            ["year", "class_id", "class_pt", "class_en", "pixels", "area_ha",
             "area_pct"],
        ))

    sheets.append(ods.sheet_from_dataframe("resumo_por_classe",
                                           _buffer_summary(history)))
    sheets.append(_classes_sheet())

    label = identity.get("conglomerado") or f"{p.lat:.4f}_{p.lon:.4f}".replace("-", "s")
    name = f"naturametrics_ponto_{label}_{_timestamp()}.ods"
    data = ods.write(sheets)
    logger.info("Study-point workbook: %s (%s KiB)", name, len(data) // 1024)
    return data, name


# --------------------------------------------------------------------------- #
# Conglomerado selection
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class SelectionSpec:
    """Which conglomerados the export covers, and which tables it carries.

    A selection is named in one of two ways, and the rest of this module does not
    care which: by the four map filters, or by an explicit list of conglomerados
    the user clicked. ``conglomerados`` wins when set — it is the more specific
    statement of intent, and the filters are still recorded in the metadata so
    the file says what was on screen at the time.
    """

    region: str = ""
    uf: str = ""
    municipality: str = ""
    biome: str = ""
    #: Explicit conglomerado names, from a manual multiple selection.
    conglomerados: list[str] | None = None
    #: Which buffer radii the export covers. Fewer radii mean fewer rows, a
    #: smaller Earth Engine geometry per point, and a higher ceiling.
    radii: tuple[float, ...] = tuple(sorted(BUFFER_RADII_KM))
    include_points: bool = True
    include_pixel: bool = True
    include_buffers: bool = False

    @property
    def is_manual(self) -> bool:
        return bool(self.conglomerados)

    def filters(self) -> dict[str, str]:
        return {"region": self.region, "uf": self.uf,
                "municipality": self.municipality, "biome": self.biome}

    def collection(self):
        """The Earth Engine collection this selection refers to."""
        if self.is_manual:
            return ifn.points_by_conglomerado(self.conglomerados)
        return ifn.filtered_points(**self.filters())

    def points(self) -> list[dict[str, Any]]:
        """The local rows for this selection."""
        if self.is_manual:
            return ifn.points_named(self.conglomerados)
        return ifn.selected_points(**self.filters())

    def filter_label(self) -> str:
        parts = [v for v in (self.region, self.biome, self.uf, self.municipality) if v]
        scope = " · ".join(parts) if parts else "Brasil inteiro (sem filtro)"
        if self.is_manual:
            return (f"seleção manual de {len(self.conglomerados)} conglomerados "
                    f"(filtros do mapa: {scope})")
        return scope


def selection_pixel_frame(spec: SelectionSpec) -> tuple[pd.DataFrame, Provenance]:
    """One row per conglomerado, one column per year, holding the pixel's class.

    Streamed straight out of Earth Engine as CSV rather than assembled from
    ``getInfo``: measured at 17 479 points × 40 years = 2.3 MB in 1.9 s, which is
    why this half of the export needs no size cap at all.
    """
    import io as _io
    import urllib.request

    import ee

    from .ee_client import get_ee

    get_ee()
    years = mb.MAPBIOMAS_YEARS
    bands = [mb.band_for_year(y) for y in years]
    asset = mb.MAPBIOMAS_COLLECTIONS[mb.MAPBIOMAS_DEFAULT_COLLECTION]
    fields = ifn.field_names()
    keys = [fields["conglomerate"], fields["region"], fields["uf"],
            fields["municipality"], fields["biome"]]

    prov = Provenance(
        name="selection_point_pixel",
        dataset_id=asset,
        bands=bands,
        reducer="first",
        pixel_area_basis="n/a — single pixel per conglomerado",
        extra={"filters": spec.filter_label(), "ifn_asset": ifn.asset_id()},
    )

    started = time.time()
    url = (
        ee.Image(asset)
        .select(bands)
        .reduceRegions(collection=spec.collection(),
                       reducer=ee.Reducer.first(), scale=prov.scale_m)
        .getDownloadURL(filetype="csv", selectors=keys + bands)
    )
    with urllib.request.urlopen(url, timeout=900) as response:
        raw = response.read()

    df = pd.read_csv(_io.BytesIO(raw))
    df = df.rename(columns={
        fields["conglomerate"]: "conglomerado", fields["region"]: "regiao",
        fields["uf"]: "uf", fields["municipality"]: "municipio",
        fields["biome"]: "bioma",
    })
    df = df.rename(columns={mb.band_for_year(y): f"classe_{y}" for y in years})
    df = df.sort_values(["uf", "municipio", "conglomerado"]).reset_index(drop=True)

    prov.extra["n_conglomerados"] = len(df)
    prov.extra["elapsed_s"] = round(time.time() - started, 1)
    logger.info("Selection pixel frame: %s rows in %.1f s", len(df),
                time.time() - started)
    return df, prov


def selection_buffer_frame(
    spec: SelectionSpec,
    points: Sequence[dict[str, Any]],
    progress: Callable[[int, int], None] | None = None,
) -> tuple[pd.DataFrame, Provenance, list[str]]:
    """Buffer land-cover history for every selected conglomerado.

    Fans the *same* per-point analysis the interactive view uses out across the
    Earth Engine pool, rather than building one enormous ``reduceRegions``.
    Measured: 0.11 s/point fanned out against 0.39 s/point batched, and — more
    importantly — the numbers here are produced by the identical code path as the
    numbers on screen, so a user can check one against the other.

    Returns the frame, its provenance, and the conglomerados that failed. Partial
    failure does not abort the export: 3 bad points out of 500 should cost 3
    rows, not the file.
    """
    from .ee_concurrency import get_ee_executor

    executor = get_ee_executor()
    prov = Provenance(
        name="selection_buffer_history",
        dataset_id=mb.MAPBIOMAS_COLLECTIONS[mb.MAPBIOMAS_DEFAULT_COLLECTION],
        bands=[mb.band_for_year(y) for y in mb.MAPBIOMAS_YEARS],
        reducer="frequencyHistogram",
        pixel_area_basis="mean ee.Image.pixelArea() per buffer",
        extra={"filters": spec.filter_label(),
               "buffer_mode": BUFFER_MODE_DEFAULT,
               "n_requested": len(points)},
    )

    started = time.time()
    radii = tuple(sorted(spec.radii)) or tuple(sorted(BUFFER_RADII_KM))
    prov.extra["radii_km"] = list(radii)
    futures = {
        executor.submit(land_cover_history,
                        point(lat=row["lat"], lon=row["lon"]),
                        radii, BUFFER_MODE_DEFAULT): row
        for row in points
    }

    frames: list[pd.DataFrame] = []
    failed: list[str] = []
    degraded = 0
    done = 0

    for future in futures:
        row = futures[future]
        try:
            df, point_prov = future.result(timeout=EXPORT_POINT_TIMEOUT_S)
            if point_prov.degraded:
                degraded += 1
            if not df.empty:
                df = df.copy()
                df.insert(0, "conglomerado", row["conglomerado"])
                df.insert(1, "uf", row["uf"])
                df.insert(2, "municipio", row["municipio"])
                df.insert(3, "bioma", row["bioma"])
                frames.append(df)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Buffer export failed for %s: %s",
                           row["conglomerado"], exc)
            failed.append(str(row["conglomerado"]))
        finally:
            done += 1
            if progress:
                progress(done, len(futures))

    if frames:
        out = pd.concat(frames, ignore_index=True)
        out = _with_shares(out)
        out = out.sort_values(["conglomerado", "radius_km", "year", "area_ha"],
                              ascending=[True, True, True, False])
        out = out.reset_index(drop=True)
    else:
        out = pd.DataFrame(columns=["conglomerado", "uf", "municipio", "bioma",
                                    "radius_km", "year", "class_id", "class_pt",
                                    "class_en", "pixels", "area_ha", "area_pct"])

    if degraded:
        prov.degrade(
            f"{degraded} de {len(points)} conglomerados precisaram de nova "
            f"tentativa em escala ou tileScale maior.")
    prov.extra["n_ok"] = len(points) - len(failed)
    prov.extra["n_failed"] = len(failed)
    prov.extra["n_rows"] = len(out)
    prov.extra["elapsed_s"] = round(time.time() - started, 1)
    logger.info("Selection buffer frame: %s rows from %s points in %.1f s "
                "(%s failed)", len(out), len(points), time.time() - started,
                len(failed))
    return out, prov, failed


#: Columns of a per-radius buffer tab. ``radius_km`` is absent on purpose — the
#: tab name carries it, and dropping it saves a column across a million rows.
_BUFFER_COLUMNS = ["conglomerado", "uf", "municipio", "bioma", "year",
                   "class_id", "class_pt", "class_en", "pixels", "area_ha",
                   "area_pct"]


def _buffer_sheets(df: pd.DataFrame, radii: Sequence[float]) -> list[ods.Sheet]:
    """One tab per radius — which is what lifts the ceiling.

    A single combined tab makes the spreadsheet's row limit apply to all four
    radii together; splitting them means the limit applies to the largest radius
    alone, and the same selection fits about four times over. It also happens to
    be the more useful shape: one tab is one buffer, comparable across
    conglomerados without filtering first.

    A radius that still overflows is split further into ``…_2``, ``…_3`` rather
    than refused. The budgets in ``settings`` are estimates, and an estimate that
    is slightly low must not destroy an export that has already been paid for.
    """
    sheets: list[ods.Sheet] = []
    for radius in sorted(radii):
        name = f"buffer_{int(radius):02d}km"
        sub = df[df["radius_km"] == radius] if not df.empty else df
        if len(sub) <= EXPORT_ODS_ROWS_PER_SHEET:
            sheets.append(ods.sheet_from_dataframe(name, sub, _BUFFER_COLUMNS))
            continue
        for part, start in enumerate(
                range(0, len(sub), EXPORT_ODS_ROWS_PER_SHEET), start=1):
            chunk = sub.iloc[start:start + EXPORT_ODS_ROWS_PER_SHEET]
            sheets.append(ods.sheet_from_dataframe(
                name if part == 1 else f"{name}_{part}", chunk, _BUFFER_COLUMNS))
    return sheets


def selection_workbook(
    spec: SelectionSpec,
    points: Sequence[dict[str, Any]],
    pixel: tuple[pd.DataFrame, Provenance] | None,
    buffers: tuple[pd.DataFrame, Provenance, list[str]] | None,
) -> tuple[bytes, str]:
    """One spreadsheet covering every conglomerado the filters select."""
    provenances: list[Provenance] = []
    sheets: list[ods.Sheet] = []

    context: list[list[Any]] = [
        ["ESCOPO", "seleção manual de conglomerados" if spec.is_manual
                   else "seleção de conglomerados do IFN"],
        ["filtros", spec.filter_label()],
        ["conglomerados na seleção", len(points)],
        ["fonte dos pontos", ifn.asset_id()],
        ["", ""],
    ]

    points_df = pd.DataFrame(list(points), columns=[
        "ponto_id", "conglomerado", "regiao", "uf", "municipio", "bioma",
        "lon", "lat"])

    if spec.include_points:
        sheets.append(ods.sheet_from_dataframe("conglomerados", points_df))

    if pixel is not None:
        pixel_df, pixel_prov = pixel
        provenances.append(pixel_prov)
        sheets.append(ods.sheet_from_dataframe("pixel_por_ano", pixel_df))
        context.append(["AVISO — aba pixel_por_ano", PIXEL_CAVEAT])

    if buffers is not None:
        buffer_df, buffer_prov, failed = buffers
        provenances.append(buffer_prov)
        buffer_sheets = _buffer_sheets(buffer_df, spec.radii)
        sheets.extend(buffer_sheets)
        context.append(["raios exportados",
                        ", ".join(f"{r:g} km" for r in sorted(spec.radii))])
        context.append(["conglomerados com buffer", buffer_prov.extra.get("n_ok", 0)])
        if len(buffer_sheets) > len(spec.radii):
            context.append([
                "abas divididas",
                "Um raio passou do limite de linhas por aba e foi dividido em "
                "«…_2», «…_3». As partes são contínuas: basta empilhá-las.",
            ])
        if failed:
            # Named, not counted: "12 failed" is not actionable, a list is.
            context.append(["conglomerados que falharam", ", ".join(failed)])

    sheets.append(_classes_sheet())
    sheets.insert(0, _metadata_sheet("seleção de conglomerados", context,
                                     provenances))

    name = f"naturametrics_conglomerados_{_timestamp()}.ods"
    data = ods.write(sheets)
    logger.info("Selection workbook: %s (%s KiB, %s sheets)", name,
                len(data) // 1024, len(sheets))
    return data, name


# --------------------------------------------------------------------------- #
# How much a buffer export costs, before running it
# --------------------------------------------------------------------------- #

def rows_per_point(radii: Sequence[float]) -> int:
    """Budgeted rows one conglomerado contributes for these radii."""
    return sum(EXPORT_ROWS_PER_POINT.get(float(r), 500) for r in radii) or 1


def max_points_for(radii: Sequence[float]) -> int:
    """How many conglomerados these radii allow.

    Two independent ceilings, and the lower one wins:

    * **per sheet** — each radius gets its own tab, so what matters is the
      *largest* radius asked for, not their total;
    * **per file** — the download travels inside a WebSocket event, so the whole
      workbook has a budget of its own.
    """
    radii = [float(r) for r in radii] or list(BUFFER_RADII_KM)
    widest = max(EXPORT_ROWS_PER_POINT.get(r, 500) for r in radii)
    return max(1, min(EXPORT_ODS_ROWS_PER_SHEET // widest,
                      EXPORT_MAX_TOTAL_ROWS // rows_per_point(radii)))


def estimated_seconds(n: int) -> int:
    return max(3, int(n * EXPORT_SECONDS_PER_POINT))


def _thousands(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def buffer_cap_message(n: int, radii: Sequence[float]) -> str:
    """Why this many conglomerados will not fit — and what would.

    Names the radii that *are* within reach rather than only refusing: the
    remedy is usually "ask for one buffer instead of four", and a message that
    does not say so leaves the user to guess.
    """
    limit = max_points_for(radii)
    chosen = ", ".join(f"{r:g} km" for r in sorted(radii))

    workable = [r for r in sorted(BUFFER_RADII_KM) if max_points_for([r]) >= n]
    if workable:
        remedy = ("Cabe escolhendo um raio só: "
                  + ", ".join(f"{r:g} km" for r in workable) + ".")
    else:
        smallest = min(BUFFER_RADII_KM)
        remedy = (f"Nem um raio isolado cabe nesta seleção — o máximo é "
                  f"{_thousands(max_points_for([smallest]))} conglomerados a "
                  f"{smallest:g} km. Reduza a seleção com os filtros.")

    return (
        f"A seleção tem {_thousands(n)} conglomerados; com {chosen} o limite é "
        f"{_thousands(limit)}. {remedy} A lista de pontos e a classe do pixel "
        f"não têm limite."
    )
