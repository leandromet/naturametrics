"""The laid-out report (PDF + HTML) of the study point or the selection on screen.

doc/14: the app builds one ``report_kit.Report`` from frames it has already
computed, and the kit draws it twice — ``render_pdf`` and ``render_html`` (R4).
This module is the Naturametrics side of that contract:

* :class:`ReportData` — the state snapshot, revived into DataFrames;
* :func:`figure_specs` — the charts, built on the server by the *same*
  ``components.charts`` functions the screen uses (``fig.to_plotly_json()``),
  which the PDF path sends to the browser for ``Plotly.toImage`` (§2.7) and
  the HTML path embeds as interactive figures;
* :func:`fetch_report_maps` — the Earth Engine thumbnails (the only network
  step, run in an executor; images from the same builders as the map tiles);
* :func:`build_study_point_report` / :func:`build_selection_report` — the
  model, following the outlines of doc/14 §3a / §3b;
* :func:`render_report` and :func:`report_filename`.

It is the third export path, complementary to the per-chart icons (one figure
at a time) and the ODS workbook (every number, for reprocessing): this is the
"send someone everything, already laid out" document. Nothing is recomputed
here (doc/11 §5): every number in a table or sentence comes from the frame the
screen drew. The explanatory text lives in ``services.report_text``.
"""

from __future__ import annotations

import logging
import math
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import pandas as pd

from .. import report_kit as rk
from ..components import charts
from ..config import mapbiomas as mb
from ..config import vegetation_age as fa
from ..config.citation import APP_URL, CITATION_TEXT, DATA_SOURCES, DATA_SOURCES_EN
from ..config.settings import BUFFER_RADII_KM
from ..report_kit import maps as kmaps
from . import report_text as rt
from .change_mask import (CHANGE_COLORS, CHANGE_GAIN, CHANGE_LABELS_EN,
                          CHANGE_LABELS_PT, CHANGE_LOSS, FOREST_CODE_BASELINE_YEAR)
from .exports import APP_VERSION, _buffer_summary

logger = logging.getLogger(__name__)

ACCENT = "#1f8d49"
BRAND = rk.Brand(accent=ACCENT, app_line="umaterra · Naturametrics")
MAP_YEAR = mb.MAPBIOMAS_YEAR_END
#: Height/width of the report maps: a little flatter than the kit's 110/170 so
#: two maps with their legends share a page.
MAP_ASPECT = 0.55

#: Figure keys, in the order they appear — also the browser-capture keys.
POINT_FIGURES = ("land_cover", "age_point", "age_hist", "change", "biomass", "ibge")
SELECTION_FIGURES = ("land_cover", "age_hist", "biomass", "ibge")


@dataclass
class ReportOptions:
    """The export dialog's checkboxes (doc/14 §2.9)."""

    maps: bool = True
    figures: bool = True
    tables: bool = True
    appendix: bool = False
    gbif: bool = False


def _frame(records) -> pd.DataFrame:
    if records is None:
        return pd.DataFrame()
    if isinstance(records, pd.DataFrame):
        return records
    return pd.DataFrame(list(records)) if len(records) else pd.DataFrame()


@dataclass
class ReportData:
    """Everything one report reads, taken from state in one snapshot.

    ``kind`` is "point" or "selection"; for a selection the frames are the
    aggregate the charts show (``_mode_pick`` in state/_export.py), and the
    point-only datasets (pixel, point age, change, connectivity, GBIF) are
    empty by construction.
    """

    kind: str = "point"
    lat: float = 0.0
    lon: float = 0.0
    identity: dict = field(default_factory=dict)
    buffer_shape: str = "circle"
    active_radius: float = 0.0
    age_radius: float = 0.0
    history: pd.DataFrame = field(default_factory=pd.DataFrame)
    history_prov: dict = field(default_factory=dict)
    pixel: pd.DataFrame = field(default_factory=pd.DataFrame)
    pixel_prov: dict = field(default_factory=dict)
    age_point: pd.DataFrame = field(default_factory=pd.DataFrame)
    age_point_prov: dict = field(default_factory=dict)
    age_buffers: pd.DataFrame = field(default_factory=pd.DataFrame)
    age_buffers_prov: dict = field(default_factory=dict)
    change: dict = field(default_factory=dict)          # {radius: {loss_ha, gain_ha, stable_ha}}
    change_prov: dict = field(default_factory=dict)
    landscape_metrics: pd.DataFrame = field(default_factory=pd.DataFrame)
    landscape_metrics_prov: dict = field(default_factory=dict)
    connectivity: pd.DataFrame = field(default_factory=pd.DataFrame)
    connectivity_prov: dict = field(default_factory=dict)
    biomass: pd.DataFrame = field(default_factory=pd.DataFrame)
    biomass_prov: dict = field(default_factory=dict)
    veg_compare: pd.DataFrame = field(default_factory=pd.DataFrame)
    veg_compare_prov: dict = field(default_factory=dict)
    gbif_rows: list = field(default_factory=list)
    overlays: dict = field(default_factory=dict)       # buffer_overlays (what the map shows)
    errors: dict = field(default_factory=dict)         # dataset → error text on screen
    selection_mode: str = "sum"                        # "sum" | "full_area"
    points: list = field(default_factory=list)         # [{key, conglomerado, place, bioma, lat, lon}]
    point_frames: dict = field(default_factory=dict)   # key → that point's history records

    _FRAMES = ("history", "pixel", "age_point", "age_buffers", "landscape_metrics",
               "connectivity", "biomass", "veg_compare")

    @classmethod
    def from_snapshot(cls, snap: dict) -> "ReportData":
        kw = {k: v for k, v in (snap or {}).items() if k in cls.__dataclass_fields__}
        for name in cls._FRAMES:
            kw[name] = _frame(kw.get(name))
        kw["change"] = {float(k): v for k, v in (kw.get("change") or {}).items()}
        for name in ("history_prov", "pixel_prov", "age_point_prov", "age_buffers_prov",
                     "change_prov", "landscape_metrics_prov", "connectivity_prov",
                     "biomass_prov", "veg_compare_prov", "identity", "overlays", "errors",
                     "point_frames"):
            kw[name] = kw.get(name) or {}
        return cls(**kw)

    @property
    def is_selection(self) -> bool:
        return self.kind == "selection"

    @property
    def scope(self) -> str:
        return self.selection_mode if self.is_selection else "point"

    @property
    def n_points(self) -> int:
        return len(self.points)


# --------------------------------------------------------------------------- #
# Radii — from the data, never from the configuration (doc/14 §1, bug 2)
# --------------------------------------------------------------------------- #

def _radii_in(*frames: Optional[pd.DataFrame]) -> list[float]:
    """The radii actually present in the data — never BUFFER_RADII_KM, which
    is what the app *can* compute, not what this result holds (full-area mode
    carries only the outer radius; looping the full list drew empty figures
    for the rest). Falls back to the configured radii only when no frame says
    anything, so an empty report still reads sensibly."""
    found: set[float] = set()
    for df in frames:
        if df is not None and not df.empty and "radius_km" in df.columns:
            found.update(float(r) for r in df["radius_km"].dropna().unique())
    return sorted(found) if found else sorted(BUFFER_RADII_KM)


def _data_radii(d: ReportData) -> list[float]:
    return _radii_in(d.history, d.age_buffers, d.biomass, d.landscape_metrics,
                     d.veg_compare)


def _pick(r: float, radii: list[float]) -> float:
    """``r`` when the data has it, else the largest radius present."""
    for x in radii:
        if abs(float(x) - float(r or 0)) < 1e-9:
            return float(x)
    return float(max(radii)) if radii else float(r or 0)


def _at(df: pd.DataFrame, r: float) -> pd.DataFrame:
    if df is None or df.empty or "radius_km" not in df.columns:
        return pd.DataFrame()
    return df[df["radius_km"].astype(float) == float(r)]


# --------------------------------------------------------------------------- #
# Figures — the screen's own chart builders
# --------------------------------------------------------------------------- #

@dataclass
class FigureSpec:
    key: str
    caption: str
    fig_json: dict
    slot: str = "full"
    aspect: float = 0.56


def _ibge_matrix(df: pd.DataFrame, r: float) -> dict:
    from .ibge_vegetation import bucket_matrix
    return bucket_matrix(df, r)


def figure_specs(d: ReportData, lang: str = "pt") -> list[FigureSpec]:
    """Every chart this report can show, built from the snapshot's frames by
    the functions that draw them on screen. Only charts with data are
    returned; a section without data is reported as such, not drawn empty."""
    L = rt.text_lang(lang)
    radii = _data_radii(d)
    r = _pick(d.active_radius, radii)
    ra = _pick(d.age_radius or d.active_radius, radii)
    shape = d.buffer_shape
    specs: list[FigureSpec] = []

    def add(key, fig, caption, slot="full", aspect=0.56):
        specs.append(FigureSpec(key, caption, fig.to_plotly_json(), slot, aspect))

    if not _at(d.history, r).empty:
        add("land_cover", charts.land_cover_history_figure(d.history, r, lang=L),
            rt.tx("cap_land_cover", L, period=rt.PERIOD,
                  radius=rt.radius_label(r, shape, L)), aspect=0.62)
    if not d.is_selection and not d.age_point.empty and "age" in d.age_point.columns:
        add("age_point", charts.forest_age_line_figure(d.age_point, lang=L),
            rt.tx("cap_age_point", L), aspect=0.4)
    if not _at(d.age_buffers, ra).empty:
        add("age_hist", charts.forest_age_histogram_figure(d.age_buffers, ra, lang=L),
            rt.tx("cap_age_hist", L, radius=rt.radius_label(ra, shape, L)), aspect=0.42)
    if not d.is_selection and d.change.get(ra):
        row = d.change[ra]
        add("change", charts.change_bar_figure(row.get("loss_ha", 0.0),
                                               row.get("gain_ha", 0.0), lang=L),
            rt.tx("cap_change", L, y0=FOREST_CODE_BASELINE_YEAR, y1=MAP_YEAR,
                  radius=rt.radius_label(ra, shape, L)), slot="half", aspect=0.62)
    if not _at(d.biomass, ra).empty:
        add("biomass", charts.biomass_history_figure(d.biomass, ra, lang=L),
            rt.tx("cap_biomass", L, radius=rt.radius_label(ra, shape, L)), aspect=0.42)
    if not _at(d.veg_compare, ra).empty:
        add("ibge", charts.ibge_comparison_figure(_ibge_matrix(d.veg_compare, ra), lang=L),
            rt.tx("cap_ibge", L, radius=rt.radius_label(ra, shape, L)), aspect=0.62)
    return specs


def resolve_figures(specs: list[FigureSpec], fmt: str,
                    pngs: Optional[dict] = None, errors: Optional[dict] = None,
                    lang: str = "pt") -> dict[str, rk.Figure]:
    """Kit ``Figure`` blocks: interactive JSON for HTML, the browser's PNG
    for PDF — and for a chart the browser did not return, a stated
    placeholder, never a silent gap."""
    pngs, errors = pngs or {}, errors or {}
    out: dict[str, rk.Figure] = {}
    for s in specs:
        if fmt == "html":
            out[s.key] = rk.Figure(s.key, s.caption, s.slot, s.aspect, fig_json=s.fig_json)
            continue
        png = pngs.get(s.key)
        reason = "" if png else rt.tx("fig_not_rendered", rt.text_lang(lang),
                                      error=errors.get(s.key, "—"))
        out[s.key] = rk.Figure(s.key, s.caption, s.slot, s.aspect, png=png,
                               unavailable_reason=reason)
    return out


# --------------------------------------------------------------------------- #
# Maps (doc/14 §6)
# --------------------------------------------------------------------------- #

def _circle(lat: float, lon: float, radius_km: float, n: int = 96) -> list:
    """A geodesic circle (spherical destination formula), closed ring."""
    R = 6371.0088
    d = radius_km / R
    la, lo = math.radians(lat), math.radians(lon)
    ring = []
    for i in range(n + 1):
        b = 2 * math.pi * i / n
        lat2 = math.asin(math.sin(la) * math.cos(d) + math.cos(la) * math.sin(d) * math.cos(b))
        lon2 = lo + math.atan2(math.sin(b) * math.sin(d) * math.cos(la),
                               math.cos(d) - math.sin(la) * math.sin(lat2))
        ring.append([math.degrees(lon2), math.degrees(lat2)])
    return ring


def _poly(ring: list) -> dict:
    return {"type": "Polygon", "coordinates": [ring]}


def _fc(geoms: list) -> dict:
    return {"type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": g, "properties": {}} for g in geoms]}


@dataclass
class MapFrame:
    """What every map of this report shares: the rings, the points, the
    outline the class layers are clipped to, and the view."""

    rings: dict
    points: dict
    clip: Optional[dict]
    outer: Optional[dict]
    view: Any
    radii: list[float]
    backdrop: bool = True


def map_frame(d: ReportData) -> Optional[MapFrame]:
    """Rings and points from ``buffer_overlays`` — exactly what the map shows
    in every mode (doc/14 §1, bug 3). Multi mode's ``buffer_circle`` entries
    carry a centre and a radius and are drawn as geodesic circles here."""
    feats = (d.overlays or {}).get("features") or []
    radii = _data_radii(d)
    outer_r = max(radii) if radii else max(BUFFER_RADII_KM)
    rings: list = []
    points: list = []
    outer: list = []
    clip = None
    full_area = None
    for f in feats:
        props = f.get("properties") or {}
        role = props.get("role")
        geom = f.get("geometry") or {}
        rr = float(props.get("radius_km") or 0)
        if role in ("study_point", "selected_point") and geom.get("type") == "Point":
            points.append(geom)
        elif role == "buffer" and geom.get("type") in ("Polygon", "MultiPolygon"):
            if d.is_selection and abs(rr - outer_r) > 1e-9:
                continue          # a selection draws each point's outer ring only
            rings.append(geom)
            if abs(rr - outer_r) < 1e-9:
                outer.append(geom)
        elif role == "buffer_circle" and geom.get("type") == "Point":
            if abs(rr - outer_r) > 1e-9:
                continue
            lon, lat = geom["coordinates"][:2]
            g = _poly(_circle(float(lat), float(lon), rr))
            rings.append(g)
            outer.append(g)
            if not any(p.get("coordinates") == geom.get("coordinates") for p in points):
                points.append({"type": "Point", "coordinates": [lon, lat]})
        elif role == "full_area":
            full_area = geom
    if not d.is_selection and not rings and (d.lat or d.lon):
        for r in radii:
            g = _poly(_circle(d.lat, d.lon, r))
            rings.append(g)
            if abs(r - outer_r) < 1e-9:
                outer.append(g)
        points = points or [{"type": "Point", "coordinates": [d.lon, d.lat]}]
    if d.is_selection and not rings and not full_area:
        for p in d.points:
            if p.get("lat") is None:
                continue
            g = _poly(_circle(float(p["lat"]), float(p["lon"]), outer_r))
            rings.append(g)
            outer.append(g)
            points.append({"type": "Point", "coordinates": [float(p["lon"]), float(p["lat"])]})
    if full_area:
        rings = [full_area]
        clip = full_area
    elif not d.is_selection and outer:
        clip = outer[0]
    if not rings and not points:
        return None
    view = kmaps.MapView.from_geojson([_fc(rings + points)], "full", aspect=MAP_ASPECT)
    # A sum selection overlaps its circles; an even-odd clip to their union
    # would punch holes where two overlap, so it is shown unclipped and without
    # a backdrop (the class layer covers the whole frame).
    return MapFrame(rings=_fc(rings), points=_fc(points), clip=clip,
                    outer=outer[0] if outer else None, view=view, radii=radii,
                    backdrop=not (d.is_selection and d.selection_mode != "full_area"))


def _mapbiomas_legend(d: ReportData, lang: str, limit: int = 12) -> list[rk.LegendItem]:
    """The classes the map shows, from the frame the chart was drawn from
    (last year, outer radius), largest first."""
    radii = _data_radii(d)
    sub = _at(d.history, max(radii)) if radii else pd.DataFrame()
    if sub.empty:
        return []
    last = sub[sub["year"] == sub["year"].max()]
    areas = last.groupby("class_id")["area_ha"].sum().sort_values(ascending=False)
    items = [rk.LegendItem(mb.color(int(c)), mb.label(int(c), lang))
             for c, a in areas.items() if a > 0][:limit]
    return items


def _vectors(frame: MapFrame, lang: str, selection: bool) -> tuple[list, list]:
    """Rings (white over imagery, dark over a full-frame class map) and the
    points, plus their legend lines."""
    L = rt.text_lang(lang)
    ring_color = "#111111" if not frame.backdrop else "#ffffff"
    vectors = [rk.VectorLayer(frame.rings, stroke=ring_color, width_pt=0.9)]
    vectors.append(rk.VectorLayer(frame.points, stroke="#ffffff", fill=ACCENT,
                                  width_pt=0.7, point_radius_pt=2.6 if selection else 3.2))
    legend = [rk.LegendItem(ACCENT, rt.tx("legend_points" if selection else "legend_point", L)),
              rk.LegendItem("#666666", rt.tx("legend_buffers", L,
                                             radii=rt.radii_label(frame.radii, "circle", L)),
                            kind="line")]
    return vectors, legend


def fetch_report_maps(d: ReportData, lang: str = "pt",
                      progress: Optional[Callable[[int, int], None]] = None,
                      ) -> dict[str, Any]:
    """The report's maps as ``{key: MapComposition}``, or ``{key: error}``.

    Blocking (Earth Engine thumbnails over HTTP) — the caller runs it in an
    executor. Thumbnails are fetched concurrently; a failed class layer turns
    that map into an error string (the report states it), a failed backdrop
    only drops the imagery.
    """
    from .change_mask import change_mask_image, change_mask_vis
    from .ee_client import get_ee
    from .layers import mapbiomas_image

    get_ee()   # first, before any ee object is built (doc/11, the stale-tab lesson)
    L = rt.text_lang(lang)
    frame = map_frame(d)
    if frame is None:
        return {}
    view = frame.view
    keys = ("mapbiomas",) if d.is_selection else ("imagery", "mapbiomas", "change")

    jobs: dict[str, Callable[[], bytes]] = {}
    backdrop_attr = ""
    if frame.backdrop:
        try:
            picked = kmaps.imagery_backdrop(view, MAP_YEAR)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Report backdrop unavailable: %s", exc)
            picked = None
        if picked is not None:
            img, backdrop_attr = picked
            jobs["backdrop"] = lambda: kmaps.fetch_thumbnail(
                img, view, "jpg", cache_key=f"backdrop:{MAP_YEAR}")
    jobs["mapbiomas"] = lambda: kmaps.fetch_thumbnail(
        mapbiomas_image(MAP_YEAR).visualize(**mb.MAPBIOMAS_VIS), view, "png",
        cache_key=f"mapbiomas:{MAP_YEAR}")
    if "change" in keys:
        jobs["change"] = lambda: kmaps.fetch_thumbnail(
            change_mask_image(FOREST_CODE_BASELINE_YEAR, MAP_YEAR).visualize(
                **change_mask_vis(False)), view, "png",
            cache_key=f"change:{FOREST_CODE_BASELINE_YEAR}-{MAP_YEAR}")

    raster: dict[str, Any] = {}
    done = {"n": 0}
    lock = threading.Lock()
    total = len(jobs)

    def run(name: str):
        try:
            raster[name] = jobs[name]()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Report map layer %s failed: %s", name, exc)
            raster[name] = exc
        with lock:
            done["n"] += 1
            if progress:
                progress(done["n"], total)

    if progress:
        progress(0, total)
    with ThreadPoolExecutor(max_workers=min(4, total)) as pool:
        list(pool.map(run, list(jobs)))

    backdrop = raster.get("backdrop")
    backdrop = backdrop if isinstance(backdrop, bytes) else None
    vectors, base_legend = _vectors(frame, L, d.is_selection)
    mb_attr = "MapBiomas Coleção 10.1 (CC BY-SA 4.0)" if L == "pt" else \
        "MapBiomas Collection 10.1 (CC BY-SA 4.0)"
    out: dict[str, Any] = {}

    def attribution(*parts: str) -> str:
        return " · ".join(p for p in parts if p)

    if "imagery" in keys:
        out["imagery"] = (rk.MapComposition(
            view=view, backdrop=backdrop, vectors=vectors, legend=base_legend,
            attribution=backdrop_attr) if backdrop else
            rt.tx("map_unavailable", L, error=str(raster.get("backdrop") or "—")))
    layer = raster.get("mapbiomas")
    out["mapbiomas"] = (rk.MapComposition(
        view=view, backdrop=backdrop, overlays=[layer], vectors=vectors,
        clip_to=frame.clip, legend=_mapbiomas_legend(d, L) + base_legend,
        attribution=attribution(mb_attr, backdrop_attr if backdrop else ""))
        if isinstance(layer, bytes) else rt.tx("map_unavailable", L, error=str(layer)))
    if "change" in keys:
        layer = raster.get("change")
        labels = CHANGE_LABELS_PT if L == "pt" else CHANGE_LABELS_EN
        legend = [rk.LegendItem(CHANGE_COLORS[c], labels[c]) for c in (CHANGE_LOSS, CHANGE_GAIN)]
        out["change"] = (rk.MapComposition(
            view=view, backdrop=backdrop, overlays=[layer], vectors=vectors,
            clip_to=frame.clip, legend=legend + base_legend,
            attribution=attribution(mb_attr, backdrop_attr if backdrop else ""))
            if isinstance(layer, bytes) else rt.tx("map_unavailable", L, error=str(layer)))
    return out


# --------------------------------------------------------------------------- #
# The model
# --------------------------------------------------------------------------- #

def _meta(d: ReportData, lang: str, generated_at: Optional[datetime]) -> rk.ReportMeta:
    L = rt.text_lang(lang)
    return rk.ReportMeta(app="Naturametrics", app_url=APP_URL, app_version=APP_VERSION,
                         title=rt.tx("title_selection" if d.is_selection else "title", L),
                         subject=subject_line(d, L), lang=L,
                         generated_at=generated_at or datetime.now(timezone.utc),
                         brand=BRAND)


def subject_line(d: ReportData, lang: str = "pt") -> str:
    L = rt.text_lang(lang)
    if d.is_selection:
        key = ("subject_selection_full" if d.selection_mode == "full_area"
               else "subject_selection_sum")
        return rt.tx(key, L, n=d.n_points)
    ident = d.identity or {}
    bits = [f"{d.lat:.5f}, {d.lon:.5f}"]
    if ident.get("conglomerado"):
        bits.insert(0, str(ident["conglomerado"]))
    if ident.get("municipio"):
        bits.append(f"{ident['municipio']}/{ident.get('uf', '')}".rstrip("/"))
    return " · ".join(bits)


class _Builder:
    """Assembles one report. Each ``_sec_*`` adds its section (or not) and
    records its status for the "about this report" list."""

    def __init__(self, d: ReportData, opts: ReportOptions, lang: str,
                 figures: Optional[dict], maps: Optional[dict]):
        self.d, self.o = d, opts
        self.L = rt.text_lang(lang)
        self.radii = _data_radii(d)
        self.r = _pick(d.active_radius, self.radii)
        self.ra = _pick(d.age_radius or d.active_radius, self.radii)
        self.shape = d.buffer_shape
        if figures is None and opts.figures:
            figures = resolve_figures(figure_specs(d, self.L), "html", lang=self.L)
        self.figures = figures or {}
        self.maps = maps
        self.sections: list[rk.Section] = []
        self.contents: list[rk.ContentsItem] = []
        self.attributions: list[str] = []
        self.y0, self.y1 = mb.MAPBIOMAS_YEAR_START, mb.MAPBIOMAS_YEAR_END
        if not d.history.empty and "year" in d.history.columns:
            self.y0, self.y1 = int(d.history["year"].min()), int(d.history["year"].max())

    # ---- helpers --------------------------------------------------------- #
    def t(self, key, **kw):
        return rt.tx(key, self.L, **kw)

    def rl(self, r):
        return rt.radius_label(r, self.shape, self.L)

    def status(self, key: str, status: str, reason: str = "") -> None:
        self.contents.append(rk.ContentsItem(self.t(key), status, reason))

    def missing(self, key: str, error_key: str) -> None:
        """A section with no data: "unavailable" with the error when the
        query failed on screen, "not run" otherwise."""
        err = (self.d.errors or {}).get(error_key) or ""
        if err:
            self.status(key, "unavailable", self.t("reason_failed", error=err))
        else:
            self.status(key, "not_run", self.t("reason_no_result"))

    def fig(self, key: str) -> Optional[rk.Figure]:
        return self.figures.get(key) if self.o.figures else None

    def add(self, key: str, title_key: str, blocks: list) -> None:
        self.sections.append(rk.Section(self.t(title_key), [b for b in blocks if b], key=key))
        self.status(title_key, "included")

    # ---- identification + about ------------------------------------------ #
    def identification(self) -> rk.Section:
        d, L = self.d, self.L
        ident = d.identity or {}
        radii_txt = rt.radii_label(self.radii, self.shape, L)
        shape_txt = self.t("shape_square" if self.shape == "square" else "shape_circle")
        computed = str((d.history_prov or {}).get("computed_at") or "")
        computed = f"{computed[:16].replace('T', ' ')} UTC" if computed else "—"
        if d.is_selection:
            rows = [
                (self.t("kv_n_points"), str(d.n_points)),
                (self.t("kv_view_mode"),
                 self.t("view_full_area" if d.selection_mode == "full_area" else "view_sum")),
                (self.t("kv_buffers"), self.t("kv_buffers_value", radii=radii_txt, shape=shape_txt)),
                (self.t("kv_period"), f"{self.y0}–{self.y1}"),
                (self.t("kv_analysis_time"), computed),
            ]
            coords = [[float(p["lon"]), float(p["lat"])] for p in d.points
                      if p.get("lat") is not None]
            geom = ({"type": "MultiPoint", "coordinates": coords} if coords else
                    {"type": "Point", "coordinates": [d.lon, d.lat]})
            loc_caption = self.t("locator_caption_selection")
        else:
            src = (self.t("kv_origin_conglomerado", c=ident["conglomerado"])
                   if ident.get("conglomerado") else self.t("kv_origin_click"))
            rows = [
                (self.t("kv_coordinates"), f"{d.lat:.5f}, {d.lon:.5f}"),
                (self.t("kv_dms"), rt.dms(d.lat, d.lon)),
                (self.t("kv_origin"), src),
                (self.t("kv_uf"), ident.get("uf") or "—"),
                (self.t("kv_municipio"), ident.get("municipio") or "—"),
                (self.t("kv_bioma"), ident.get("bioma") or "—"),
                (self.t("kv_buffers"), self.t("kv_buffers_value", radii=radii_txt, shape=shape_txt)),
                (self.t("kv_period"), f"{self.y0}–{self.y1}"),
                (self.t("kv_analysis_time"), computed),
            ]
            geom = {"type": "Point", "coordinates": [d.lon, d.lat]}
            loc_caption = self.t("locator_caption")
        blocks: list = [rk.SideBySide(rk.KeyValues(rows),
                                      rk.LocatorMap(geom, loc_caption, slot="half"))]
        if d.is_selection and d.points:
            blocks.append(rk.Table(
                [self.t("h_conglomerado"), self.t("h_place"), self.t("h_bioma"),
                 self.t("h_lat"), self.t("h_lon")],
                [[p.get("conglomerado", ""), p.get("place", ""), p.get("bioma", ""),
                  p.get("lat"), p.get("lon")] for p in d.points],
                self.t("points_caption"), align=["l", "l", "l", "r", "r"],
                decimals=[None, None, None, 5, 5], max_rows=60))
        return rk.Section(self.t("sec_identification"), blocks, key="identification")

    def about(self) -> rk.Section:
        d = self.d
        radii_txt = rt.radii_label(self.radii, self.shape, self.L)
        if d.is_selection:
            para = self.t("about_selection", n=d.n_points, period=f"{self.y0}–{self.y1}",
                          radii=radii_txt, active=self.rl(self.r),
                          mode=self.t("view_full_area" if d.selection_mode == "full_area"
                                      else "view_sum"))
        else:
            para = self.t("about_point", period=f"{self.y0}–{self.y1}", radii=radii_txt,
                          active=self.rl(self.r),
                          shape=self.t("shape_square" if self.shape == "square"
                                       else "shape_circle"))
        blocks: list = []
        if d.is_selection and d.selection_mode != "full_area":
            # First, before anything is read: every total below is a sum.
            blocks.append(rk.Callout(self.t("overlap_caveat"), "warning",
                                     self.t("overlap_title")))
        blocks += [rk.ContentsList(self.contents), rk.Paragraph(para)]
        return rk.Section(self.t("sec_about"), blocks, key="about")

    # ---- maps ------------------------------------------------------------- #
    def sec_maps(self) -> None:
        if not self.o.maps:
            self.status("sec_maps", "excluded", self.t("reason_unticked"))
            return
        if self.maps is None:
            self.status("sec_maps", "unavailable", self.t("reason_maps_offline"))
            return
        L, blocks, errors = self.L, [], []
        radii_txt = rt.radii_label(self.radii, self.shape, L)
        captions = {
            "imagery": self.t("map_imagery_caption", radii=radii_txt),
            "mapbiomas": (self.t("map_mapbiomas_caption_selection", year=MAP_YEAR,
                                 radius=self.rl(max(self.radii)))
                          if self.d.is_selection else
                          self.t("map_mapbiomas_caption", year=MAP_YEAR)),
            "change": self.t("map_change_caption", y0=FOREST_CODE_BASELINE_YEAR, y1=MAP_YEAR),
        }
        for key in ("imagery", "mapbiomas", "change"):
            comp = self.maps.get(key)
            if comp is None:
                continue
            if isinstance(comp, rk.MapComposition):
                blocks.append(rk.MapFigure(comp, captions[key]))
                for part in (comp.attribution or "").split(" · "):
                    if part and part not in self.attributions:
                        self.attributions.append(part)
            else:
                errors.append(str(comp))
                blocks.append(rk.Paragraph(f"*{comp}*"))
        if not any(isinstance(b, rk.MapFigure) for b in blocks):
            self.status("sec_maps", "unavailable",
                        self.t("reason_maps_failed", error="; ".join(errors) or "—"))
            return
        self.add("maps", "sec_maps", blocks)

    # ---- analysis sections ------------------------------------------------ #
    def sec_land_cover(self) -> None:
        d, L = self.d, self.L
        if d.history.empty:
            self.missing("sec_land_cover", "analysis")
            return
        blocks: list = [rk.Paragraph(self.t("intro_land_cover", period=f"{self.y0}–{self.y1}")),
                        self.fig("land_cover")]
        if self.o.tables:
            nat = d.history["class_id"].astype(int).isin(mb.NATURAL_VEGETATION)
            rows = []
            for r in self.radii:
                sub = _at(d.history, r)
                if sub.empty:
                    continue
                natv = sub[nat.loc[sub.index]].groupby("year")["area_ha"].sum()
                tot = sub.groupby("year")["area_ha"].sum()
                a0, a1 = float(natv.get(self.y0, 0.0)), float(natv.get(self.y1, 0.0))
                t0, t1 = float(tot.get(self.y0, 0.0)), float(tot.get(self.y1, 0.0))
                rows.append([self.rl(r), a0, a0 / t0 * 100 if t0 else None,
                             a1, a1 / t1 * 100 if t1 else None, a1 - a0])
            blocks.append(rk.Table(
                [self.t("h_buffer"), self.t("h_natural_y", y=self.y0), self.t("h_pct_y", y=self.y0),
                 self.t("h_natural_y", y=self.y1), self.t("h_pct_y", y=self.y1),
                 self.t("h_change_ha")], rows,
                self.t("tab_natural_by_radius", y0=self.y0, y1=self.y1),
                align=["l", "r", "r", "r", "r", "r"], decimals=[None, 1, 1, 1, 1, 1]))
            summary = _buffer_summary(d.history)
            sub = summary[summary["radius_km"].astype(float) == self.r]
            crow = [[mb.label(int(c), L), a0, a1, v, p] for c, a0, a1, v, p in zip(
                sub["class_id"], sub["area_primeiro_ano_ha"], sub["area_ultimo_ano_ha"],
                sub["variacao_ha"], sub["variacao_pct"]) if (a0 or a1)]
            blocks.append(rk.Table(
                [self.t("h_class"), self.t("h_area_y", y=self.y0), self.t("h_area_y", y=self.y1),
                 self.t("h_change_ha"), self.t("h_change_pct")], crow,
                self.t("tab_classes", radius=self.rl(self.r), y0=self.y0, y1=self.y1),
                align=["l", "r", "r", "r", "r"], decimals=[None, 1, 1, 1, 1]))
        blocks.append(rk.Paragraph(
            rt.land_cover_sentence(d.history, self.r, L, d.scope, d.n_points, self.shape)
            + " " + rt.natural_sentence(d.history, self.r, L)))
        self.add("land_cover", "sec_land_cover", blocks)

    def sec_pixel(self) -> None:
        d, L = self.d, self.L
        if d.is_selection:
            self.status("sec_pixel", "unavailable", self.t("reason_not_for_selection"))
            return
        runs = rt.pixel_runs(d.pixel, L)
        if not runs:
            self.missing("sec_pixel", "analysis")
            return
        blocks: list = [rk.Paragraph(self.t("intro_pixel"))]
        if self.o.tables:
            blocks.append(rk.Table(
                [self.t("h_years"), self.t("h_n_years"), self.t("h_class")],
                [[f"{a}–{b}" if a != b else str(a), b - a + 1, c] for a, b, c in runs],
                self.t("tab_pixel_runs"), align=["l", "r", "l"], max_rows=60))
        blocks.append(rk.Paragraph(rt.pixel_sentence(d.pixel, L)))
        blocks.append(rk.Callout(self.t("pixel_caveat"), "note", self.t("pixel_caveat_title")))
        self.add("pixel", "sec_pixel", blocks)

    def sec_age(self) -> None:
        from .vegetation_age import age_summary
        d, L = self.d, self.L
        has_point = not d.is_selection and not d.age_point.empty
        if d.age_buffers.empty and not has_point:
            self.missing("sec_age", "age")
            return
        blocks: list = [rk.Paragraph(self.t("intro_age", c=fa.CENSORED_AGE))]
        if has_point:
            blocks.append(self.fig("age_point"))
        blocks.append(self.fig("age_hist"))
        summary = age_summary(d.age_buffers, self.ra, lang=L) if not d.age_buffers.empty else {}
        if self.o.tables and not d.age_buffers.empty:
            rows = []
            for r in self.radii:
                s = age_summary(d.age_buffers, r, lang=L)
                if s:
                    rows.append([self.rl(r), s["total_natural_area_ha"], s["median_dated_age"],
                                 s["censored_area_ha"], s["censored_pct"]])
            blocks.append(rk.Table(
                [self.t("h_buffer"), self.t("h_total_natural"), self.t("h_median_age"),
                 self.t("h_censored_ha"), self.t("h_censored_pct")], rows,
                self.t("tab_age"), align=["l", "r", "r", "r", "r"],
                decimals=[None, 1, 0, 1, 1]))
        text = " ".join(x for x in (
            rt.age_point_sentence(d.age_point, L) if has_point else "",
            rt.age_sentence(summary, self.ra, L, d.scope, d.n_points, self.shape)) if x)
        if text:
            blocks.append(rk.Paragraph(text))
        self.add("age", "sec_age", blocks)

    def sec_change(self) -> None:
        d = self.d
        if d.is_selection:
            self.status("sec_change", "unavailable", self.t("reason_not_for_selection"))
            return
        if not d.change:
            self.missing("sec_change", "age")
            return
        blocks: list = [rk.Paragraph(self.t("intro_change", y0=FOREST_CODE_BASELINE_YEAR,
                                            y1=MAP_YEAR)), self.fig("change")]
        if self.o.tables:
            blocks.append(rk.Table(
                [self.t("h_buffer"), self.t("h_loss"), self.t("h_gain"), self.t("h_stable")],
                [[self.rl(r), v.get("loss_ha"), v.get("gain_ha"), v.get("stable_ha")]
                 for r, v in sorted(d.change.items())],
                self.t("tab_change", y0=FOREST_CODE_BASELINE_YEAR, y1=MAP_YEAR),
                align=["l", "r", "r", "r"], decimals=[None, 1, 1, 1]))
        blocks.append(rk.Paragraph(rt.change_sentence(
            d.change.get(self.ra) or {}, self.ra, self.L, FOREST_CODE_BASELINE_YEAR, self.shape)))
        self.add("change", "sec_change", blocks)

    def sec_biomass(self) -> None:
        d, L = self.d, self.L
        if d.biomass.empty:
            self.missing("sec_biomass", "biomass")
            return
        blocks: list = [rk.Paragraph(self.t("intro_biomass")), self.fig("biomass")]
        if self.o.tables and "agb_mean_mgha" in d.biomass.columns:
            radii = [r for r in self.radii if not _at(d.biomass, r).empty]
            piv = d.biomass.pivot_table(index="year", columns="radius_km",
                                        values="agb_mean_mgha", aggfunc="first")
            rows = [[str(int(y))] + [float(piv.at[y, r]) if r in piv.columns and piv.at[y, r] == piv.at[y, r]
                                else None for r in radii] for y in piv.index]
            blocks.append(rk.Table([self.t("h_year")] + [self.rl(r) for r in radii], rows,
                                   self.t("tab_biomass"), align=["l"] + ["r"] * len(radii),
                                   decimals=[None] + [1] * len(radii),
                                   note=self.t("biomass_no_sd") if (
                                       d.is_selection and d.selection_mode != "full_area") else ""))
        blocks.append(rk.Paragraph(rt.biomass_sentence(d.biomass, self.ra, L, d.scope,
                                                       d.n_points, self.shape)))
        self.add("biomass", "sec_biomass", blocks)

    def sec_landscape(self) -> None:
        d, L = self.d, self.L
        if d.landscape_metrics.empty:
            self.missing("sec_landscape", "landscape")
        else:
            blocks: list = [rk.Paragraph(self.t("intro_landscape"))]
            if self.o.tables:
                cols = [("area_ha", "h_area_ha", 1), ("patches", "h_patches", 0),
                        ("patch_density", "h_patch_density", 2),
                        ("largest_patch_pct", "h_largest_pct", 1),
                        ("edge_density", "h_edge_density", 1), ("meff_ha", "h_meff", 1),
                        ("shannon", "h_shannon", 2), ("simpson_evenness", "h_evenness", 2)]
                cols = [c for c in cols if c[0] in d.landscape_metrics.columns]
                rows = [[self.rl(float(rec["radius_km"]))] + [rec.get(c[0]) for c in cols]
                        for rec in d.landscape_metrics.sort_values("radius_km").to_dict("records")]
                blocks.append(rk.Table([self.t("h_buffer")] + [self.t(c[1]) for c in cols], rows,
                                       self.t("tab_landscape"), align=["l"] + ["r"] * len(cols),
                                       decimals=[None] + [c[2] for c in cols]))
            blocks.append(rk.Paragraph(rt.landscape_sentence(
                d.landscape_metrics, self.r, L, d.scope, d.n_points, self.shape)))
            self.add("landscape", "sec_landscape", blocks)
        # Connectivity — the costly on-demand metric, point only.
        if d.is_selection:
            self.status("sec_connectivity", "unavailable", self.t("reason_not_for_selection"))
        elif d.connectivity.empty:
            err = (d.errors or {}).get("connectivity")
            if err:
                self.status("sec_connectivity", "unavailable", self.t("reason_failed", error=err))
            else:
                self.status("sec_connectivity", "not_run", self.t("reason_connectivity_button"))
        else:
            blocks = [rk.Paragraph(self.t("intro_connectivity"))]
            if self.o.tables:
                rows = [[self.rl(float(rec["radius_km"])), rec.get("n_fragments"),
                         rec.get("enn_mean_m"), rec.get("enn_median_m")]
                        for rec in d.connectivity.sort_values("radius_km").to_dict("records")]
                blocks.append(rk.Table(
                    [self.t("h_buffer"), self.t("h_fragments"), self.t("h_enn_mean"),
                     self.t("h_enn_median")], rows, self.t("tab_connectivity"),
                    align=["l", "r", "r", "r"], decimals=[None, 0, 0, 0]))
            blocks.append(rk.Paragraph(rt.connectivity_sentence(d.connectivity, self.r, L,
                                                                self.shape)))
            self.add("connectivity", "sec_connectivity", blocks)

    def sec_ibge(self) -> None:
        d, L = self.d, self.L
        if d.veg_compare.empty:
            self.missing("sec_ibge", "veg_compare")
            return
        blocks: list = [rk.Paragraph(self.t("intro_ibge")), self.fig("ibge")]
        if self.o.tables:
            rows = []
            for r in self.radii:
                if _at(d.veg_compare, r).empty:
                    continue
                m = _ibge_matrix(d.veg_compare, r)
                rows.append([self.rl(r), m.get("forest_ibge"), m.get("forest_mb"),
                             m.get("natural_ibge"), m.get("natural_mb")])
            blocks.append(rk.Table(
                [self.t("h_buffer"), self.t("h_forest_ibge"), self.t("h_forest_mb"),
                 self.t("h_natural_ibge"), self.t("h_natural_mb")], rows,
                self.t("tab_ibge"), align=["l", "r", "r", "r", "r"],
                decimals=[None, 1, 1, 1, 1]))
        blocks.append(rk.Paragraph(rt.ibge_sentence(_ibge_matrix(d.veg_compare, self.ra), self.ra,
                                                    L, d.scope, d.n_points, self.shape)))
        self.add("ibge", "sec_ibge", blocks)

    def sec_gbif(self) -> None:
        d, L = self.d, self.L
        if d.is_selection:
            self.status("sec_gbif", "unavailable", self.t("reason_point_only"))
            return
        if not self.o.gbif:
            self.status("sec_gbif", "excluded", self.t("reason_unticked"))
            return
        rows = [r for r in (d.gbif_rows or []) if isinstance(r, dict)]
        if not rows:
            err = (d.errors or {}).get("gbif")
            if err:
                self.status("sec_gbif", "unavailable", self.t("reason_failed", error=err))
            else:
                self.status("sec_gbif", "not_run", self.t("reason_gbif_run"))
            return
        rows = sorted(rows, key=lambda r: float(r.get("radius_km") or 0))
        blocks: list = [rk.Paragraph(self.t("intro_gbif"))]
        if self.o.tables:
            blocks.append(rk.Table(
                [self.t("h_buffer"), self.t("h_records"), self.t("h_richness")],
                [[self.rl(float(r["radius_km"])), r.get("total"), r.get("richness")]
                 for r in rows], self.t("tab_gbif"), align=["l", "r", "r"],
                decimals=[None, 0, 0]))
        active = next((r for r in rows if abs(float(r["radius_km"]) - self.r) < 1e-9), rows[-1])
        species = (active.get("species") or [])[:15]
        if self.o.tables and species:
            blocks.append(rk.Table(
                [self.t("h_species"), self.t("h_records")],
                [[s.get("name", ""), s.get("count")] for s in species if isinstance(s, dict)],
                self.t("tab_gbif_species", radius=self.rl(float(active["radius_km"]))),
                align=["l", "r"], decimals=[None, 0]))
        blocks.append(rk.Paragraph(rt.gbif_sentence(active, L, self.shape)))
        self.add("gbif", "sec_gbif", blocks)

    def sec_per_point(self) -> None:
        d, L = self.d, self.L
        if not d.point_frames or not d.points:
            return
        rows, shares = [], []
        y0 = y1 = None
        for p in d.points:
            df = _frame(d.point_frames.get(p.get("key")) or d.point_frames.get(
                p.get("conglomerado")))
            sub = _at(df, self.r)
            if sub.empty:
                rows.append([p.get("conglomerado", ""), p.get("place", ""), p.get("bioma", ""),
                             None, None, None])
                continue
            nat = sub["class_id"].astype(int).isin(mb.NATURAL_VEGETATION)
            tot = sub.groupby("year")["area_ha"].sum()
            natv = sub[nat].groupby("year")["area_ha"].sum()
            a, b = int(sub["year"].min()), int(sub["year"].max())
            y0, y1 = a, b
            s0 = float(natv.get(a, 0.0)) / float(tot.get(a, 0.0)) * 100 if tot.get(a) else None
            s1 = float(natv.get(b, 0.0)) / float(tot.get(b, 0.0)) * 100 if tot.get(b) else None
            shares.append(s1)
            rows.append([p.get("conglomerado", ""), p.get("place", ""), p.get("bioma", ""),
                         s0, s1, (s1 - s0) if s0 is not None and s1 is not None else None])
        y0, y1 = y0 or self.y0, y1 or self.y1
        blocks: list = [rk.Paragraph(self.t("intro_per_point", radius=self.rl(self.r)))]
        if self.o.tables:
            blocks.append(rk.Table(
                [self.t("h_conglomerado"), self.t("h_place"), self.t("h_bioma"),
                 self.t("h_pct_y", y=y0), self.t("h_pct_y", y=y1), "Δ (p.p.)"], rows,
                self.t("tab_per_point", radius=self.rl(self.r)),
                align=["l", "l", "l", "r", "r", "r"], decimals=[None, None, None, 1, 1, 1],
                max_rows=60))
        blocks.append(rk.Paragraph(rt.per_point_sentence(shares, self.r, y1, L, self.shape)))
        self.add("per_point", "sec_per_point", blocks)

    # ---- closing sections ------------------------------------------------- #
    def provenance(self) -> None:
        d = self.d
        provs = [d.history_prov, d.age_buffers_prov, d.landscape_metrics_prov,
                 d.biomass_prov, d.veg_compare_prov]
        if not d.is_selection:      # point-only products never describe a selection
            provs[1:1] = [d.pixel_prov, d.age_point_prov]
            provs[4:4] = [d.change_prov]
            provs.append(d.connectivity_prov)
        rows = [p for p in provs if p]
        self.add("provenance", "sec_provenance", [rk.ProvenanceTable(rows)])

    def sources(self) -> None:
        L = self.L
        text = CITATION_TEXT if L == "pt" else (
            CITATION_TEXT.replace("história de uso da terra e análise da paisagem",
                                  "land-use history and landscape analysis")
            .replace("Disponível em:", "Available at:"))
        wanted = ["mapbiomas.org", "doi.org/10.5285", "ibge.gov.br", "earthengine.google.com"]
        if self.d.is_selection or (self.d.identity or {}).get("conglomerado"):
            wanted.append("dados.florestal.gov.br")
        if any(s.key == "gbif" for s in self.sections):
            wanted.append("gbif.org")
        if any("Landsat" in a for a in self.attributions):
            wanted.append("LANDSAT_COMPOSITES")
        table = DATA_SOURCES if L == "pt" else DATA_SOURCES_EN
        seen: set = set()
        srcs = []
        for name, detail, url in table:
            if any(w in url for w in wanted) and (name, url) not in seen:
                seen.add((name, url))
                srcs.append(f"{name} — {detail} {url}")
        self.add("sources", "sec_sources",
                 [rk.Paragraph(self.t("citation_note")),
                  rk.Citation(text, srcs, list(self.attributions))])

    def appendix(self) -> None:
        if not self.o.appendix:
            self.status("sec_appendix", "excluded", self.t("reason_unticked"))
            return
        d, L = self.d, self.L
        blocks: list = []
        if not d.history.empty:
            summary = _buffer_summary(d.history)
            rows = [[self.rl(float(r)), mb.label(int(c), L), a0, a1, v, p]
                    for r, c, a0, a1, v, p in zip(
                        summary["radius_km"], summary["class_id"], summary["area_primeiro_ano_ha"],
                        summary["area_ultimo_ano_ha"], summary["variacao_ha"],
                        summary["variacao_pct"]) if (a0 or a1)]
            blocks.append(rk.Table(
                [self.t("h_buffer"), self.t("h_class"), self.t("h_area_y", y=self.y0),
                 self.t("h_area_y", y=self.y1), self.t("h_change_ha"), self.t("h_change_pct")],
                rows, self.t("tab_app_classes", y0=self.y0, y1=self.y1),
                align=["l", "l", "r", "r", "r", "r"], decimals=[None, None, 1, 1, 1, 1],
                max_rows=500))
        if not d.age_buffers.empty and "age" in d.age_buffers.columns:
            agg = (d.age_buffers.groupby(["radius_km", "age", "censored"], as_index=False)
                   ["area_ha"].sum().sort_values(["radius_km", "age"]))
            rows = [[self.rl(float(r)), int(a), self.t("yes") if bool(c) else self.t("no"), ha]
                    for r, a, c, ha in zip(agg["radius_km"], agg["age"], agg["censored"],
                                           agg["area_ha"]) if ha > 0]
            blocks.append(rk.Table(
                [self.t("h_buffer"), self.t("h_age"), self.t("h_censored"), self.t("h_area_ha")],
                rows, self.t("tab_app_age"), align=["l", "r", "l", "r"],
                decimals=[None, 0, None, 1], max_rows=500))
        if not blocks:
            self.status("sec_appendix", "not_run", self.t("reason_no_result"))
            return
        self.sections.append(rk.Section(self.t("sec_appendix"), blocks, key="appendix"))
        self.status("sec_appendix", "included")

    # ---- assembly --------------------------------------------------------- #
    def build(self, generated_at: Optional[datetime]) -> rk.Report:
        self.sec_maps()
        self.sec_land_cover()
        if self.d.is_selection:
            self.sec_age()
            self.sec_biomass()
            self.sec_landscape()
            self.sec_ibge()
            self.sec_per_point()
            # Point-only datasets, listed so the reader knows they exist.
            self.sec_change()
            self.sec_pixel()
            self.sec_gbif()
        else:
            self.sec_pixel()
            self.sec_age()
            self.sec_change()
            self.sec_biomass()
            self.sec_landscape()
            self.sec_ibge()
            self.sec_gbif()
        self.provenance()
        self.sources()
        self.appendix()
        head = [self.identification(), self.about()]
        return rk.Report(_meta(self.d, self.L, generated_at), head + self.sections)


def build_study_point_report(d: ReportData, opts: Optional[ReportOptions] = None,
                             lang: str = "pt", figures: Optional[dict] = None,
                             maps: Optional[dict] = None,
                             generated_at: Optional[datetime] = None) -> rk.Report:
    """doc/14 §3a. ``figures`` — ``{key: rk.Figure}`` from
    :func:`resolve_figures` (None: interactive figures from the frames);
    ``maps`` — :func:`fetch_report_maps` output (None: maps not fetched)."""
    d.kind = "point"
    return _Builder(d, opts or ReportOptions(), lang, figures, maps).build(generated_at)


def build_selection_report(d: ReportData, opts: Optional[ReportOptions] = None,
                           lang: str = "pt", figures: Optional[dict] = None,
                           maps: Optional[dict] = None,
                           generated_at: Optional[datetime] = None) -> rk.Report:
    """doc/14 §3b — the aggregate of a manual multi-selection."""
    d.kind = "selection"
    return _Builder(d, opts or ReportOptions(), lang, figures, maps).build(generated_at)


def build_report(d: ReportData, opts: Optional[ReportOptions] = None, lang: str = "pt",
                 figures: Optional[dict] = None, maps: Optional[dict] = None,
                 generated_at: Optional[datetime] = None) -> rk.Report:
    fn = build_selection_report if d.is_selection else build_study_point_report
    return fn(d, opts, lang, figures, maps, generated_at)


def render_report(report: rk.Report, fmt: str) -> bytes:
    return rk.render_html(report) if fmt == "html" else rk.render_pdf(report)


def report_filename(d: ReportData, fmt: str, when: Optional[datetime] = None) -> str:
    """``naturametrics_<slug>_<YYYYMMDD-HHMM>.<pdf|html>`` (doc/14 §2.9)."""
    when = when or datetime.now(timezone.utc)
    if d.is_selection:
        slug = f"selecao_{d.n_points}"
    else:
        slug = str((d.identity or {}).get("conglomerado") or "") or \
            f"{d.lat:.4f}_{d.lon:.4f}".replace("-", "s")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", slug).strip("_") or "relatorio"
    ext = "html" if fmt == "html" else "pdf"
    return f"naturametrics_{slug}_{when.strftime('%Y%m%d-%H%M')}.{ext}"

