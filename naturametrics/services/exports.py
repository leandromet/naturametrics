"""Building the downloadable spreadsheets.

Two exports, deliberately separate because they answer different questions:

* **the study point** — everything computed about the one location on screen:
  its own pixel's 40-year class series, plus the land-cover history of each of
  the four buffers. Small, always available once an analysis has run.
* **the conglomerado selection** — the same measurements across every IFN point
  the current filters select. The single-pixel half is cheap at any size; the
  buffer half is not, and its cost depends on which radii are asked for — but it
  is reported rather than refused (see :func:`buffer_estimate`).

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
from ..config import vegetation_age as va
from ..config.citation import APP_URL, CITATION_TEXT, DATA_SOURCES
from ..config.settings import (
    BUFFER_MODE_DEFAULT, BUFFER_RADII_KM, EXPORT_AGE_ROWS_PER_POINT_PER_RADIUS,
    EXPORT_BYTES_PER_ROW, EXPORT_CHANGE_ROWS_PER_POINT_PER_RADIUS,
    EXPORT_MAX_BUFFER_POINTS, EXPORT_ODS_ROWS_PER_SHEET, EXPORT_POINT_TIMEOUT_S,
    EXPORT_ROWS_PER_POINT, EXPORT_SECONDS_PER_POINT, EXPORT_WARN_FILE_MB,
)
from . import ifn, ods
from .buffers import BufferShape
from .change_mask import FOREST_CODE_BASELINE_YEAR, change_stats
from .geo import Point, point
from .mapbiomas_history import (
    full_area_land_cover_history, land_cover_history, point_pixel_series,
)
from .provenance import Provenance
from .vegetation_age import buffer_forest_age_histogram, full_area_forest_age_histogram

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
    age_point: pd.DataFrame | None = None,
    age_point_prov: Provenance | None = None,
    age_buffers: pd.DataFrame | None = None,
    age_buffers_prov: Provenance | None = None,
    change: dict[float, dict[str, float]] | None = None,
    change_prov: Provenance | None = None,
    buffer_shape: BufferShape = "circle",
) -> tuple[bytes, str]:
    """One spreadsheet for the location currently under analysis.

    Returns ``(bytes, filename)``. Nothing is recomputed here — the history is
    the frame already on screen, so the file and the chart cannot disagree
    (doc/11 §5). The vegetation-age and change-mask arguments are optional and
    default to empty: the "Baixar dados" button is reachable as soon as the
    land-cover history has an answer (``has_result``), which can be a moment
    before the age panel's own fetch finishes — an empty tab with its own note
    is the honest result of asking for data that has not arrived yet, not an
    error.
    """
    identity = identity or {}
    history = _with_shares(history)
    age_point = age_point if age_point is not None else pd.DataFrame()
    age_buffers = age_buffers if age_buffers is not None else pd.DataFrame()
    change = change or {}

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
        ["formato dos buffers", buffer_shape],
        ["anos (uso da terra)", f"{mb.MAPBIOMAS_YEAR_START}–{mb.MAPBIOMAS_YEAR_END}"],
        ["anos (idade da vegetação)", f"{va.DSV_YEAR_START}–{va.DSV_YEAR_END}"],
        ["classe censurada (idade)", va.censored_label()],
        ["", ""],
        ["AVISO — abas de pixel", PIXEL_CAVEAT],
    ]
    if age_point.empty and age_buffers.empty:
        context.append([
            "AVISO — abas de idade/mudança",
            "Ainda não calculadas quando este arquivo foi gerado — tente "
            "baixar novamente após o painel «Idade da vegetação» carregar.",
        ])

    provenances = [pixel_prov, history_prov]
    if age_point_prov is not None:
        provenances.append(age_point_prov)
    if age_buffers_prov is not None:
        provenances.append(age_buffers_prov)
    if change_prov is not None:
        provenances.append(change_prov)

    sheets = [
        _metadata_sheet("ponto de estudo", context, provenances),
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

    sheets.append(ods.sheet_from_dataframe(
        "ponto_idade", age_point,
        ["year", "age", "censored", "class_id", "class_pt"]))

    for radius in sorted(BUFFER_RADII_KM):
        sub = (age_buffers[age_buffers["radius_km"] == radius]
               if not age_buffers.empty else age_buffers)
        sheets.append(ods.sheet_from_dataframe(
            f"idade_{int(radius):02d}km", sub,
            ["age", "bin", "censored", "pixels", "area_ha"]))

    change_rows = [
        {"radius_km": r, "perda_ha": round(v["loss_ha"], 4),
         "regeneracao_ha": round(v["gain_ha"], 4),
         "estavel_ha": round(v["stable_ha"], 4)}
        for r, v in sorted(change.items())
    ]
    sheets.append(ods.sheet_from_dataframe(
        f"mudanca_{FOREST_CODE_BASELINE_YEAR}_{mb.MAPBIOMAS_YEAR_END}",
        pd.DataFrame.from_records(
            change_rows, columns=["radius_km", "perda_ha", "regeneracao_ha", "estavel_ha"]),
    ))

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
    """Which points the export covers, and which tables it carries.

    A selection is named in one of three ways, and the rest of this module does
    not care which: by the four map filters, by an explicit list of conglomerados
    the user clicked, or by a pasted coordinate list (services.user_points).
    ``user_points`` wins over ``conglomerados``, which wins over the filters —
    each is a more specific statement of intent than the last, and the filters
    are still recorded in the metadata so the file says what was on screen.
    """

    region: str = ""
    uf: str = ""
    municipality: str = ""
    biome: str = ""
    #: Explicit conglomerado names, from a manual multiple selection.
    conglomerados: list[str] | None = None
    #: A pasted coordinate list — [{"id", "lat", "lon"}, ...]. These are not IFN
    #: conglomerados: no região/UF/município/bioma exists for them, so every
    #: downstream table carries those columns empty rather than guessing.
    user_points: list[dict[str, Any]] | None = None
    #: Which buffer radii the export covers. Fewer radii mean fewer rows, a
    #: smaller Earth Engine geometry per point, and a higher ceiling.
    radii: tuple[float, ...] = tuple(sorted(BUFFER_RADII_KM))
    buffer_shape: BufferShape = "circle"
    include_points: bool = True
    include_pixel: bool = True
    include_buffers: bool = False
    #: Bounding box enclosing every selected point's buffer, analysed as one
    #: region instead of summed per point. Only meaningful for a manual
    #: selection (see ``is_manual``) — a filter selection can span thousands
    #: of points across a whole state, where a bounding box is neither cheap
    #: nor a meaningful region.
    include_full_area: bool = False

    @property
    def is_user_points(self) -> bool:
        return bool(self.user_points)

    @property
    def is_manual(self) -> bool:
        return bool(self.conglomerados) and not self.is_user_points

    def filters(self) -> dict[str, str]:
        return {"region": self.region, "uf": self.uf,
                "municipality": self.municipality, "biome": self.biome}

    def collection(self):
        """The Earth Engine collection this selection refers to."""
        if self.is_user_points:
            import ee
            return ee.FeatureCollection([
                ee.Feature(ee.Geometry.Point(p["lon"], p["lat"]), {"id": p["id"]})
                for p in self.user_points
            ])
        if self.is_manual:
            return ifn.points_by_conglomerado(self.conglomerados)
        return ifn.filtered_points(**self.filters())

    def points(self) -> list[dict[str, Any]]:
        """The local rows for this selection — same shape regardless of source,
        so every fan-out downstream (selection_buffer_frame and friends) reads
        ``row["conglomerado"]``/``row["uf"]``/etc. without needing to know which
        kind of selection this is."""
        if self.is_user_points:
            return [
                {"ponto_id": p["id"], "conglomerado": p["id"], "regiao": "",
                 "uf": "", "municipio": "", "bioma": "", "lon": p["lon"],
                 "lat": p["lat"]}
                for p in self.user_points
            ]
        if self.is_manual:
            return ifn.points_named(self.conglomerados)
        return ifn.selected_points(**self.filters())

    def filter_label(self) -> str:
        if self.is_user_points:
            return f"lista de coordenadas enviada pelo usuário ({len(self.user_points)} pontos)"
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

    if spec.is_user_points:
        # A pasted list has no IFN identity to select on — just the "id"
        # property this module gave the FeatureCollection in collection().
        id_key = "id"
        keys = [id_key]
    else:
        fields = ifn.field_names()
        keys = [fields["conglomerate"], fields["region"], fields["uf"],
                fields["municipality"], fields["biome"]]

    prov = Provenance(
        name="selection_point_pixel",
        dataset_id=asset,
        bands=bands,
        reducer="first",
        pixel_area_basis="n/a — single pixel per conglomerado",
        extra={"filters": spec.filter_label(),
               "ifn_asset": None if spec.is_user_points else ifn.asset_id()},
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
    if spec.is_user_points:
        df = df.rename(columns={id_key: "conglomerado"})
        for col in ("regiao", "uf", "municipio", "bioma"):
            df[col] = ""
    else:
        df = df.rename(columns={
            fields["conglomerate"]: "conglomerado", fields["region"]: "regiao",
            fields["uf"]: "uf", fields["municipality"]: "municipio",
            fields["biome"]: "bioma",
        })
    df = df.rename(columns={mb.band_for_year(y): f"classe_{y}" for y in years})
    df = df[["conglomerado", "regiao", "uf", "municipio", "bioma"]
            + [f"classe_{y}" for y in years]]
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
               "buffer_shape": spec.buffer_shape,
               "n_requested": len(points)},
    )

    started = time.time()
    radii = tuple(sorted(spec.radii)) or tuple(sorted(BUFFER_RADII_KM))
    prov.extra["radii_km"] = list(radii)
    futures = {
        executor.submit(land_cover_history,
                        point(lat=row["lat"], lon=row["lon"]),
                        radii, BUFFER_MODE_DEFAULT, spec.buffer_shape): row
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


def selection_age_frame(
    spec: SelectionSpec,
    points: Sequence[dict[str, Any]],
    progress: Callable[[int, int], None] | None = None,
) -> tuple[pd.DataFrame, Provenance, list[str]]:
    """Vegetation-age histogram for every selected conglomerado.

    Same fan-out shape as :func:`selection_buffer_frame`, over the DSV-based age
    counter (services.vegetation_age) instead of the MapBiomas coverage series —
    a **separate pass**, not folded into that one: different Earth Engine asset,
    different failure mode, and one hiccup must not take the other down (the same
    reasoning that keeps ``age_error`` separate from ``analysis_error`` on the
    interactive side, state/_analysis.py).
    """
    from .ee_concurrency import get_ee_executor

    executor = get_ee_executor()
    prov = Provenance(
        name="selection_vegetation_age",
        dataset_id=va.DSV_ASSET,
        bands=[va.dsv_band_for_year(va.DSV_YEAR_END)],
        reducer="frequencyHistogram",
        pixel_area_basis="mean ee.Image.pixelArea() per buffer",
         extra={"filters": spec.filter_label(), "buffer_mode": BUFFER_MODE_DEFAULT,
             "buffer_shape": spec.buffer_shape,
               "n_requested": len(points), "reference_year": va.DSV_YEAR_END,
               "censored_age": va.CENSORED_AGE},
    )

    started = time.time()
    radii = tuple(sorted(spec.radii)) or tuple(sorted(BUFFER_RADII_KM))
    prov.extra["radii_km"] = list(radii)
    futures = {
        executor.submit(buffer_forest_age_histogram,
                        point(lat=row["lat"], lon=row["lon"]),
                        radii, BUFFER_MODE_DEFAULT, spec.buffer_shape): row
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
            logger.warning("Age export failed for %s: %s", row["conglomerado"], exc)
            failed.append(str(row["conglomerado"]))
        finally:
            done += 1
            if progress:
                progress(done, len(futures))

    if frames:
        out = pd.concat(frames, ignore_index=True)
        out = out.sort_values(["conglomerado", "radius_km", "age"]).reset_index(drop=True)
    else:
        out = pd.DataFrame(columns=["conglomerado", "uf", "municipio", "bioma",
                                    "radius_km", "age", "bin", "censored",
                                    "pixels", "area_ha", "color"])

    if degraded:
        prov.degrade(
            f"{degraded} de {len(points)} conglomerados precisaram de nova "
            f"tentativa em escala ou tileScale maior.")
    prov.extra["n_ok"] = len(points) - len(failed)
    prov.extra["n_failed"] = len(failed)
    prov.extra["n_rows"] = len(out)
    prov.extra["elapsed_s"] = round(time.time() - started, 1)
    logger.info("Selection age frame: %s rows from %s points in %.1f s "
                "(%s failed)", len(out), len(points), time.time() - started,
                len(failed))
    return out, prov, failed


def selection_change_frame(
    spec: SelectionSpec,
    points: Sequence[dict[str, Any]],
    progress: Callable[[int, int], None] | None = None,
) -> tuple[pd.DataFrame, Provenance, list[str]]:
    """Natural-vegetation loss/gain since the Forest Code baseline, per point.

    The cheapest of the three fan-outs: change_stats already returns every
    requested radius from a single call, so this is one future per point, not
    one per (point, radius).
    """
    from .ee_concurrency import get_ee_executor

    executor = get_ee_executor()
    prov = Provenance(
        name="selection_change_mask",
        dataset_id=mb.MAPBIOMAS_COLLECTIONS[mb.MAPBIOMAS_DEFAULT_COLLECTION],
        bands=[mb.band_for_year(FOREST_CODE_BASELINE_YEAR),
               mb.band_for_year(mb.MAPBIOMAS_YEAR_END)],
        reducer="frequencyHistogram + mean(pixelArea)",
        pixel_area_basis="mean ee.Image.pixelArea() per buffer",
         extra={"filters": spec.filter_label(), "buffer_mode": BUFFER_MODE_DEFAULT,
             "buffer_shape": spec.buffer_shape,
               "n_requested": len(points), "year_from": FOREST_CODE_BASELINE_YEAR,
               "year_to": mb.MAPBIOMAS_YEAR_END},
    )

    started = time.time()
    radii = tuple(sorted(spec.radii)) or tuple(sorted(BUFFER_RADII_KM))
    prov.extra["radii_km"] = list(radii)
    futures = {
        executor.submit(change_stats, point(lat=row["lat"], lon=row["lon"]), radii,
                mode=BUFFER_MODE_DEFAULT, shape=spec.buffer_shape):
        row for row in points
    }

    records: list[dict[str, Any]] = []
    failed: list[str] = []
    done = 0

    for future in futures:
        row = futures[future]
        try:
            per_radius, _point_prov = future.result(timeout=EXPORT_POINT_TIMEOUT_S)
            for radius, vals in per_radius.items():
                records.append({
                    "conglomerado": row["conglomerado"], "uf": row["uf"],
                    "municipio": row["municipio"], "bioma": row["bioma"],
                    "radius_km": radius,
                    "perda_ha": round(vals["loss_ha"], 4),
                    "regeneracao_ha": round(vals["gain_ha"], 4),
                    "estavel_ha": round(vals["stable_ha"], 4),
                })
        except Exception as exc:  # noqa: BLE001
            logger.warning("Change export failed for %s: %s", row["conglomerado"], exc)
            failed.append(str(row["conglomerado"]))
        finally:
            done += 1
            if progress:
                progress(done, len(futures))

    out = pd.DataFrame.from_records(
        records, columns=["conglomerado", "uf", "municipio", "bioma", "radius_km",
                          "perda_ha", "regeneracao_ha", "estavel_ha"])
    if not out.empty:
        out = out.sort_values(["conglomerado", "radius_km"]).reset_index(drop=True)

    prov.extra["n_ok"] = len(points) - len(failed)
    prov.extra["n_failed"] = len(failed)
    prov.extra["n_rows"] = len(out)
    prov.extra["elapsed_s"] = round(time.time() - started, 1)
    logger.info("Selection change frame: %s rows from %s points in %.1f s "
                "(%s failed)", len(out), len(points), time.time() - started,
                len(failed))
    return out, prov, failed


def selection_full_area_frame(
    spec: SelectionSpec,
    points: Sequence[dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame, Provenance, Provenance]:
    """Land-cover and forest-age tables over the bounding box enclosing every
    selected point's buffer — the export counterpart of
    ``state._conglomerado.compute_full_area``.

    Not a fan-out: this is one Earth Engine call per table, over every point
    at once, rather than one per point — the whole reason "full area" exists
    is to replace N per-point queries (and the overlap they double-count)
    with a single region.
    """
    pts = [point(lat=row["lat"], lon=row["lon"]) for row in points]
    radii = tuple(sorted(spec.radii)) or tuple(sorted(BUFFER_RADII_KM))

    started = time.time()
    hist_df, hist_prov = full_area_land_cover_history(pts, radii, spec.buffer_shape)
    age_df, age_prov = full_area_forest_age_histogram(pts, radii, spec.buffer_shape)
    hist_prov.extra["elapsed_s"] = round(time.time() - started, 1)
    logger.info("Selection full-area frame: %s history rows, %s age rows from "
                "%s points in %.1f s", len(hist_df), len(age_df), len(points),
                time.time() - started)
    return hist_df, age_df, hist_prov, age_prov


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


#: Columns of a per-radius age tab.
_AGE_COLUMNS = ["conglomerado", "uf", "municipio", "bioma", "age", "bin",
               "censored", "pixels", "area_ha"]


def _age_sheets(df: pd.DataFrame, radii: Sequence[float]) -> list[ods.Sheet]:
    """One tab per radius, named ``idade_XXkm`` — same shape as _buffer_sheets.

    At these row counts (at most CENSORED_AGE distinct rows per point per
    radius — config.vegetation_age) splitting essentially never triggers: even
    6 000 points at the cap is 6000×38 ≈ 228 000 rows, well under
    EXPORT_ODS_ROWS_PER_SHEET. The split logic is kept anyway, at negligible
    cost, so a future change to the age model cannot silently turn a slightly
    wrong row estimate into a failed export instead of a split sheet.
    """
    sheets: list[ods.Sheet] = []
    for radius in sorted(radii):
        name = f"idade_{int(radius):02d}km"
        sub = df[df["radius_km"] == radius] if not df.empty else df
        if len(sub) <= EXPORT_ODS_ROWS_PER_SHEET:
            sheets.append(ods.sheet_from_dataframe(name, sub, _AGE_COLUMNS))
            continue
        for part, start in enumerate(
                range(0, len(sub), EXPORT_ODS_ROWS_PER_SHEET), start=1):
            chunk = sub.iloc[start:start + EXPORT_ODS_ROWS_PER_SHEET]
            sheets.append(ods.sheet_from_dataframe(
                name if part == 1 else f"{name}_{part}", chunk, _AGE_COLUMNS))
    return sheets


#: Columns of the change-mask tab. One row per (conglomerado, radius) — never
#: split, since a selection at the cap is, at most, points × radii rows (a few
#: tens of thousands), nowhere near the sheet limit.
_CHANGE_COLUMNS = ["conglomerado", "uf", "municipio", "bioma", "radius_km",
                   "perda_ha", "regeneracao_ha", "estavel_ha"]

#: Columns of the full-area tabs. No conglomerado/uf/municipio/bioma — these
#: describe one region (the bounding box), not a per-point row, and at
#: ≤5 radii × ~40 years × ~15 classes they never approach the sheet limit, so
#: unlike _buffer_sheets/_age_sheets there is no per-radius split.
_FULL_AREA_HISTORY_COLUMNS = ["radius_km", "year", "class_id", "class_pt",
                              "class_en", "pixels", "area_ha", "area_pct"]
_FULL_AREA_AGE_COLUMNS = ["radius_km", "age", "bin", "censored", "pixels", "area_ha"]


def selection_workbook(
    spec: SelectionSpec,
    points: Sequence[dict[str, Any]],
    pixel: tuple[pd.DataFrame, Provenance] | None,
    buffers: tuple[pd.DataFrame, Provenance, list[str]] | None,
    age: tuple[pd.DataFrame, Provenance, list[str]] | None = None,
    change: tuple[pd.DataFrame, Provenance, list[str]] | None = None,
    full_area: tuple[pd.DataFrame, pd.DataFrame, Provenance, Provenance] | None = None,
) -> tuple[bytes, str]:
    """One spreadsheet covering every conglomerado the filters select."""
    provenances: list[Provenance] = []
    sheets: list[ods.Sheet] = []

    context: list[list[Any]] = [
        ["ESCOPO", (
            "lista de coordenadas enviada pelo usuário" if spec.is_user_points
            else "seleção manual de conglomerados" if spec.is_manual
            else "seleção de conglomerados do IFN"
        )],
        ["filtros", spec.filter_label()],
        ["pontos na seleção", len(points)],
        ["fonte dos pontos",
         "colado pelo usuário (services.user_points)" if spec.is_user_points
         else ifn.asset_id()],
        ["formato dos buffers", spec.buffer_shape],
        ["", ""],
    ]

    points_df = pd.DataFrame(list(points), columns=[
        "ponto_id", "conglomerado", "regiao", "uf", "municipio", "bioma",
        "lon", "lat"])

    if spec.include_points:
        # Same columns either way (region/uf/municipio/bioma just come back
        # empty for a pasted list — see SelectionSpec.points()), but the tab
        # itself is misnamed calling a user's own points "conglomerados".
        sheets.append(ods.sheet_from_dataframe(
            "pontos" if spec.is_user_points else "conglomerados", points_df))

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
            context.append(["conglomerados que falharam (uso da terra)", ", ".join(failed)])

    if age is not None:
        age_df, age_prov, age_failed = age
        provenances.append(age_prov)
        age_sheets = _age_sheets(age_df, spec.radii)
        sheets.extend(age_sheets)
        context.append(["classe censurada (idade)", va.censored_label()])
        context.append(["conglomerados com idade", age_prov.extra.get("n_ok", 0)])
        if age_failed:
            context.append(["conglomerados que falharam (idade)", ", ".join(age_failed)])

    if change is not None:
        change_df, change_prov, change_failed = change
        provenances.append(change_prov)
        sheets.append(ods.sheet_from_dataframe(
            f"mudanca_{FOREST_CODE_BASELINE_YEAR}_{mb.MAPBIOMAS_YEAR_END}",
            change_df, _CHANGE_COLUMNS))
        context.append(["conglomerados com mudança", change_prov.extra.get("n_ok", 0)])
        if change_failed:
            context.append(["conglomerados que falharam (mudança)", ", ".join(change_failed)])

    if full_area is not None:
        fa_hist_df, fa_age_df, fa_hist_prov, fa_age_prov = full_area
        provenances.append(fa_hist_prov)
        provenances.append(fa_age_prov)
        sheets.append(ods.sheet_from_dataframe(
            "area_total_uso_solo", _with_shares(fa_hist_df),
            _FULL_AREA_HISTORY_COLUMNS))
        sheets.append(ods.sheet_from_dataframe(
            "area_total_idade_veg", fa_age_df, _FULL_AREA_AGE_COLUMNS))
        outer_radius = fa_hist_prov.extra.get("outer_radius_km")
        bbox = fa_hist_prov.extra.get("bbox_wgs84")
        context.append([
            "AVISO — abas area_total_*",
            "Uma única caixa delimitadora (oeste/sul/leste/norte), no raio "
            "mais externo exportado, envolvendo o buffer de cada ponto "
            "selecionado — sem sobreposição contada duas vezes, mas "
            "incluindo também a área entre os conglomerados, que não "
            "pertence a nenhum buffer individual. Ver as abas "
            "«conglomerados»/buffer_*km para o valor ponto a ponto.",
        ])
        if outer_radius is not None:
            context.append(["raio da caixa delimitadora (km)", outer_radius])
        if bbox:
            context.append(["caixa delimitadora (O,S,L,N)",
                            ", ".join(f"{v:.5f}" for v in bbox)])

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
    """Budgeted rows one conglomerado contributes for these radii, across all
    three buffer tables — land-cover history, vegetation age and the change
    mask — since a buffer export now always includes all three (state/_export.py
    download_selection fans out all three together whenever ``exp_buffers`` is
    on)."""
    land_cover = sum(EXPORT_ROWS_PER_POINT.get(float(r), 500) for r in radii)
    age = len(radii) * EXPORT_AGE_ROWS_PER_POINT_PER_RADIUS
    change = len(radii) * EXPORT_CHANGE_ROWS_PER_POINT_PER_RADIUS
    return (land_cover + age + change) or 1


def estimated_seconds(n: int) -> int:
    return max(3, int(n * EXPORT_SECONDS_PER_POINT))


def estimated_file_mb(n: int, radii: Sequence[float]) -> float:
    return n * rows_per_point(radii) * EXPORT_BYTES_PER_ROW / 1_000_000


def _thousands(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def buffer_estimate(n: int, radii: Sequence[float]) -> dict[str, Any]:
    """What a buffer export of this size will cost — never whether it is allowed.

    Nothing here refuses anything. The only hard limit in the format is rows per
    sheet, and :func:`_buffer_sheets` handles that by splitting; a file-size cap
    would be a constraint invented rather than observed. So this reports, and the
    user decides.

    ``heavy`` marks the point where the *delivery* becomes the risk rather than
    the computation: the file travels as a base64 ``data:`` URI held whole in
    memory at both ends. ``over_limit`` is the one thing that does refuse — see
    ``settings.EXPORT_MAX_BUFFER_POINTS``, which is set from the size of the
    largest biome rather than from a guess about file sizes.
    """
    radii = [float(r) for r in radii] or list(BUFFER_RADII_KM)
    rows = n * rows_per_point(radii)
    megabytes = estimated_file_mb(n, radii)
    widest = max(EXPORT_ROWS_PER_POINT.get(r, 500) for r in radii)
    return {
        "points": n,
        "rows": rows,
        "megabytes": megabytes,
        "seconds": estimated_seconds(n),
        # One land-cover tab per radius (plus however many extra parts a radius
        # needs), one age tab per radius (never splits in practice — see
        # _age_sheets), and one combined change-mask tab.
        "tabs": sum(max(1, -(-(n * EXPORT_ROWS_PER_POINT.get(r, 500))
                             // EXPORT_ODS_ROWS_PER_SHEET)) for r in radii)
                + len(radii) + 1,
        "split": n * widest > EXPORT_ODS_ROWS_PER_SHEET,
        "heavy": megabytes > EXPORT_WARN_FILE_MB,
        "over_limit": n > EXPORT_MAX_BUFFER_POINTS,
    }


def buffer_estimate_message(n: int, radii: Sequence[float]) -> str:
    """The cost, in the user's terms. Advisory: nothing here blocks the export."""
    est = buffer_estimate(n, radii)
    seconds = est["seconds"]
    when = (f"{seconds // 60} min {seconds % 60} s" if seconds >= 60
            else f"{seconds} s")
    chosen = ", ".join(f"{r:g} km" for r in sorted(radii))

    size = (f"~{est['megabytes']:.0f} MB" if est["megabytes"] >= 1
            else f"~{est['megabytes'] * 1000:.0f} KB")
    tabs = "1 aba" if est["tabs"] == 1 else f"{est['tabs']} abas"

    if est["over_limit"]:
        return (
            f"A seleção tem {_thousands(n)} conglomerados; o limite para dados "
            f"de buffer (uso da terra, idade da vegetação e mudança) é "
            f"{_thousands(EXPORT_MAX_BUFFER_POINTS)} — o suficiente para "
            f"qualquer bioma inteiro (o maior, a Amazônia, tem 5.801). Reduza a "
            f"seleção com os filtros. A lista de pontos e a classe do pixel não "
            f"têm limite: saem para os 17.479 conglomerados."
        )

    text = (f"≈ {when} para {_thousands(n)} conglomerados (uso da terra, idade "
            f"da vegetação e mudança) · ~{_thousands(est['rows'])} linhas · "
            f"{size} · {tabs} ({chosen}).")
    if est["split"]:
        text += (" Um raio passa do máximo de linhas por aba e será dividido em "
                 "«…_2», «…_3» — as partes são contínuas.")
    if est["heavy"]:
        text += (f" Arquivo grande: o download é entregue de uma vez pelo "
                 f"navegador, e acima de ~{EXPORT_WARN_FILE_MB} MB pode ficar "
                 f"lento ou falhar.")
        # Only worth suggesting when there is something to drop.
        if len(radii) > 1:
            text += " Exportar um raio só reduz bastante."
    return text
