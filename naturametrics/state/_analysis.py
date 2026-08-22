"""Land-cover history analysis: run it, hold the result, expose it to charts."""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any

import plotly.graph_objects as go
import reflex as rx

from ..components.charts import (
    change_bar_figure, forest_age_histogram_figure, forest_age_line_figure,
    land_cover_history_figure,
)
from ..config.settings import BUFFER_MODE_DEFAULT, BUFFER_RADII_KM
from ..services.buffers import buffer_geojson
from ..services.change_mask import change_stats
from ..services.landscape_metrics import landscape_metrics
from ..services.vegetation_age import age_summary, buffer_forest_age_histogram, point_forest_age_series
from ..services.geo import CoordinateError, point
from ..services.mapbiomas_history import land_cover_history, point_pixel_series

logger = logging.getLogger(__name__)


class AnalysisMixin(rx.State, mixin=True):
    """The MapBiomas history for the current study point."""

    analysis_running: bool = False
    analysis_error: str = ""
    has_result: bool = False

    selected_radius: float = 10.0
    normalise_chart: bool = False

    #: Serialised long-format result. Backend-only: it is up to ~1 300 rows and
    #: only the figure needs to cross the wire.
    _history: list[dict[str, Any]] = []
    _provenance: dict[str, Any] = {}

    #: The study point's own 30 m pixel, one row per year. Measured alongside the
    #: buffers rather than on demand at export time: it is a 0.5 s call issued in
    #: parallel with a 1 s one, so it is free in wall-clock, and it means the
    #: export never has to make the user wait for something the app could
    #: already have known.
    _pixel: list[dict[str, Any]] = []
    _pixel_provenance: dict[str, Any] = {}

    #: Token for the in-flight run. A click that lands while an older analysis is
    #: still running must not have its result overwritten by that older run
    #: (doc/06 §5b, "cancel superseded work").
    _run_token: int = 0

    buffer_overlays: dict[str, Any] = {}

    # --- forest age (services.vegetation_age, doc/10) --------------------------- #
    #: Fetched alongside the land-cover history above but kept in its own error
    #: channel: a hiccup in the age estimator must not take down the land-use
    #: chart that already succeeded, and vice versa.
    age_running: bool = False
    age_error: str = ""
    #: "Ponto" (the line chart) or a radius label (the histogram). Point mode has
    #: no meaning for a multi-selection sum, so multi mode is steered away from it
    #: — see age_tab_options.
    selected_age_radius: str = "Ponto"

    _age_point: list[dict[str, Any]] = []
    _age_point_provenance: dict[str, Any] = {}
    _age_buffers: list[dict[str, Any]] = []
    _age_buffers_provenance: dict[str, Any] = {}

    #: services.change_mask.change_stats: loss/gain/stable hectares per buffer,
    #: 2008→2024 (the Forest Code baseline). Keyed by ``f"{radius_km:g}"`` — plain
    #: JSON-safe strings, not the float itself. Single-point only for now, same
    #: as the point-age line above: no multi-selection sum yet.
    _change_stats: dict[str, dict[str, float]] = {}
    _change_provenance: dict[str, Any] = {}
    landscape_metrics_running: bool = False
    landscape_metrics_error: str = ""
    _landscape_metrics: list[dict[str, Any]] = []
    _landscape_metrics_provenance: dict[str, Any] = {}
    selected_age_view: str = "age"

    @rx.event(background=True)
    async def run_analysis(self, lat: float, lon: float):
        """Compute the land-cover history for a freshly chosen point."""
        async with self:
            self._run_token += 1
            token = self._run_token
            self.analysis_running = True
            self.analysis_error = ""
            self.has_result = False
            self.landscape_metrics_running = True
            self.landscape_metrics_error = ""
            self._landscape_metrics = []
            self._landscape_metrics_provenance = {}

        loop = asyncio.get_running_loop()
        try:
            p = point(lat=lat, lon=lon)
            history_task = loop.run_in_executor(
                None, land_cover_history, p, BUFFER_RADII_KM,
                BUFFER_MODE_DEFAULT, self.buffer_shape)
            pixel_task = loop.run_in_executor(None, point_pixel_series, p)
            (df, prov), (pixel_df, pixel_prov) = await asyncio.gather(
                history_task, pixel_task)
        except CoordinateError as exc:
            async with self:
                if token == self._run_token:
                    self.analysis_running = False
                    self.analysis_error = str(exc)
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Analysis failed")
            async with self:
                if token == self._run_token:
                    self.analysis_running = False
                    self.analysis_error = self.tr["err_earth_engine_query"].format(
                        exc=exc)
            return

        async with self:
            if token != self._run_token:
                logger.info("Discarding superseded analysis for %s", p)
                return
            self._history = df.to_dict("records")
            self._provenance = prov.to_dict()
            self._pixel = pixel_df.to_dict("records")
            self._pixel_provenance = pixel_prov.to_dict()
            self.analysis_running = False
            self.has_result = not df.empty
            if df.empty:
                self.analysis_error = self.tr["err_no_landcover"]
            self.age_running = True
            self.age_error = ""

        # A separate try/except on purpose: the land-use chart above already has
        # its answer by this point, and an Earth Engine hiccup specific to the DSV
        # asset (services/vegetation_age.py) must not blank out a result that worked.
        try:
            age_point_task = loop.run_in_executor(None, point_forest_age_series, p)
            age_buffer_task = loop.run_in_executor(
                None, buffer_forest_age_histogram, p, BUFFER_RADII_KM,
                BUFFER_MODE_DEFAULT, self.buffer_shape)
            # services.change_mask.change_stats — 2008→2024 loss/gain per buffer,
            # shown as the small bar next to the age summary. Cheap (~1-2 s) and
            # unrelated in failure mode to the age counter above, but it lives in
            # the same panel and the same "vegetation over time" question, so it
            # shares this try/except rather than getting a third error channel.
            change_task = loop.run_in_executor(
                None, functools.partial(
                    change_stats, p, BUFFER_RADII_KM,
                    mode=BUFFER_MODE_DEFAULT, shape=self.buffer_shape))
            metrics_task = loop.run_in_executor(
                None, landscape_metrics, p, BUFFER_RADII_KM,
                BUFFER_MODE_DEFAULT, self.buffer_shape)
            (age_df, age_prov), (age_buf_df, age_buf_prov), (change, change_prov), \
                (metrics_df, metrics_prov) = await asyncio.gather(
                    age_point_task, age_buffer_task, change_task, metrics_task)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Forest-age analysis failed")
            async with self:
                if token == self._run_token:
                    self.age_running = False
                    self.age_error = self.tr["err_vegetation_age_failed"].format(
                        exc=exc)
                    self.landscape_metrics_running = False
                    self.landscape_metrics_error = str(exc)
                    self._landscape_metrics = []
                    self._landscape_metrics_provenance = {}
            return

        async with self:
            if token != self._run_token:
                return
            self._age_point = age_df.to_dict("records")
            self._age_point_provenance = age_prov.to_dict()
            self._age_buffers = age_buf_df.to_dict("records")
            self._age_buffers_provenance = age_buf_prov.to_dict()
            self._change_stats = {f"{r:g}": v for r, v in change.items()}
            self._change_provenance = change_prov.to_dict()
            self._landscape_metrics = metrics_df.to_dict("records")
            self._landscape_metrics_provenance = metrics_prov.to_dict()
            self.landscape_metrics_running = False
            self.age_running = False
            if age_buf_df.empty and age_df.empty:
                self.age_error = self.tr["err_no_vegetation_age"]

    def set_selected_radius(self, value: str | list[str]):
        """Set the buffer whose history is charted.

        The annotation must cover the FULL union the trigger can emit
        (``str | list[str]``) — Reflex checks that the handler accepts every
        shape the component might send, and refuses to build the page otherwise.
        The segmented control sends the item label, e.g. "5 km".
        """
        raw = value[0] if isinstance(value, (list, tuple)) and value else value
        try:
            num = float(str(raw).split(" km")[0].strip())
            self.selected_radius = num / 2.0 if self.buffer_shape == "square" else num
        except (TypeError, ValueError):
            pass

    def toggle_normalise(self, checked: bool):
        self.normalise_chart = checked

    def set_selected_age_radius(self, value: str | list[str]):
        """"Ponto" or a radius label — see selected_age_radius."""
        raw = value[0] if isinstance(value, (list, tuple)) and value else value
        self.selected_age_radius = str(raw)

    def set_selected_age_view(self, value: str | list[str]):
        raw = value[0] if isinstance(value, (list, tuple)) and value else value
        self.selected_age_view = str(raw)

    # ---------------------------------------------------------------------- #
    # Derived
    # ---------------------------------------------------------------------- #

    def _chart_records(self) -> list[dict[str, Any]]:
        """The rows the chart and the summary read.

        One switch, used by every derived value, so the chart, the legend and the
        provenance line can never end up describing different selections.
        """
        if self.multi_mode and self.multi_view_mode == "full_area" and self._multi_bbox_history:
            return self._multi_bbox_history
        if self.multi_mode and self._multi_history:
            return self._multi_history
        return self._history

    @rx.var(cache=True)
    def _chart_radius(self) -> float:
        """The radius the chart actually reads — the outer/largest radius in
        full-area mode (there is only the one box, see services.buffers.
        full_area_bbox), otherwise whatever the radius selector is set to."""
        if self.multi_mode and self.multi_view_mode == "full_area":
            return max(BUFFER_RADII_KM)
        return self.selected_radius

    @rx.var(cache=True)
    def history_figure(self) -> go.Figure:
        import pandas as pd

        df = pd.DataFrame(self._chart_records())
        return land_cover_history_figure(
            df, self._chart_radius, lang=self.language,
            normalise=self.normalise_chart
        )

    @rx.var(cache=True)
    def radius_options(self) -> list[str]:
        return [self._radius_label(r) for r in BUFFER_RADII_KM]

    @rx.var(cache=True)
    def selected_radius_label(self) -> str:
        return self._radius_label(self.selected_radius)

    def _radius_label(self, r: float) -> str:
        """A buffer's on-screen label — the number is the *shown* extent, not
        necessarily the internal ``radius_km`` key: a square's side is double
        its radius (services.buffers), so the label doubles it too. What the
        number means ("square side" vs. "circle radius") is spelled out once,
        as separate caption text next to the row — see buffer_extent_caption —
        rather than repeated inside every button."""
        value = 2 * r if self.buffer_shape == "square" else r
        return f"{value:g} km"

    @rx.var(cache=True)
    def full_area_radius_label(self) -> str:
        """The one radius full-area mode reads — shown in place of the radius
        selector, which has nothing to switch between once there is only the
        single outer box (services.buffers.full_area_bbox)."""
        return self._radius_label(max(BUFFER_RADII_KM))

    @rx.var(cache=True)
    def buffer_extent_caption(self) -> str:
        """Caption shown once, next to the last (largest) radius button."""
        key = "buffer_caption_square" if self.buffer_shape == "square" else "buffer_caption_circle"
        return self.tr[key]

    @rx.var(cache=True)
    def summary_rows(self) -> list[dict[str, str]]:
        """Top classes in the latest year, for the panel beside the chart."""
        import pandas as pd

        df = pd.DataFrame(self._chart_records())
        if df.empty or "radius_km" not in df.columns:
            return []
        sub = df[df["radius_km"] == self._chart_radius]
        if sub.empty:
            return []
        latest = sub[sub["year"] == sub["year"].max()]
        total = latest["area_ha"].sum()
        rows = latest.nlargest(6, "area_ha")
        name_col = "class_pt" if self.language == "pt" else "class_en"
        return [
            {
                "name": str(r[name_col]),
                "color": str(r["color"]),
                "area": (f"{r['area_ha']:,.0f} ha" if self.language != "pt"
                         else f"{r['area_ha']:,.0f} ha".replace(",", ".")),
                "pct": f"{(r['area_ha'] / total * 100):.1f}%",
            }
            for _, r in rows.iterrows()
        ]

    @rx.var(cache=True)
    def provenance_line(self) -> str:
        full_area = (self.multi_mode and self.multi_view_mode == "full_area"
                     and self._multi_bbox_history)
        multi = self.multi_mode and self._multi_history
        if full_area:
            p = self._multi_bbox_provenance
        elif multi:
            p = self._multi_provenance
        else:
            p = self._provenance
        if not p:
            return ""
        degraded = self.tr["provenance_degraded"] if p.get("degraded") else ""
        # The overlap warning belongs here rather than in a tooltip: it is the
        # one thing that makes a sum over sampling units easy to misread. The
        # full-area caveat is the mirror image — no overlap, but it covers
        # land outside any individual buffer too.
        note = ""
        if full_area:
            n = len(self.multi_points)
            note = self.tr["provenance_full_area_one" if n == 1
                            else "provenance_full_area_many"].format(n=n)
        elif multi:
            n = len(self.multi_points)
            note = self.tr["provenance_summed_one" if n == 1
                            else "provenance_summed_many"].format(n=n)
        return (
            f"MapBiomas {p.get('extra', {}).get('collection', '')} · "
            f"{len(p.get('bands', []))} {self.tr['years_unit']} · {p.get('scale_m')} m · "
            f"{p.get('reducer')}{degraded}{note}"
        )

    # --- forest age ----------------------------------------------------- #

    def _age_buffer_records(self) -> list[dict[str, Any]]:
        """Same switch as _chart_records, for the age histogram."""
        if (self.multi_mode and self.multi_view_mode == "full_area"
                and self._multi_bbox_age_history):
            return self._multi_bbox_age_history
        if self.multi_mode and self._multi_age_history:
            return self._multi_age_history
        return self._age_buffers

    @rx.var(cache=True)
    def age_has_result(self) -> bool:
        return bool(self._age_point) or bool(self._age_buffers) or bool(self._multi_age_history)

    @rx.var(cache=True)
    def landscape_metrics_has_result(self) -> bool:
        return bool(self._landscape_metrics) and not self.multi_mode

    @rx.var(cache=True)
    def landscape_metrics_rows(self) -> list[dict[str, str]]:
        rows = []
        for record in self._landscape_metrics:
            rows.append({
                "buffer": self._radius_label(float(record["radius_km"])),
                "area": f'{record["area_ha"]:,.1f}',
                "patches": f'{record["patches"]:,.0f}',
                "patch_density": f'{record["patch_density"]:.2f}',
                "largest": f'{record["largest_patch_pct"]:.1f}%',
                "edge": f'{record["edge_density"]:.1f}',
                "shannon": f'{record["shannon"]:.2f}',
                "simpson": f'{record["simpson"]:.2f}',
                "evenness": f'{record["simpson_evenness"]:.2f}',
            })
        return rows

    @rx.var(cache=True)
    def age_tab_options(self) -> list[str]:
        """"Ponto" only makes sense for one pixel — dropped for a multi-sum."""
        radii = [self._radius_label(r) for r in BUFFER_RADII_KM]
        return radii if (self.multi_mode and self._multi_age_history) else ["Ponto"] + radii

    @rx.var(cache=True)
    def age_effective_radius(self) -> float:
        """The radius the histogram actually reads — falls back off "Ponto" in
        multi mode rather than showing nothing just because the tab never got
        switched. In full-area mode there is only the one outer box (see
        services.buffers.full_area_bbox), so the radius tab is not read at all."""
        if self.multi_mode and self.multi_view_mode == "full_area":
            return max(BUFFER_RADII_KM)
        if self.selected_age_radius != "Ponto":
            try:
                num = float(self.selected_age_radius.split(" km")[0].strip())
                return num / 2.0 if self.buffer_shape == "square" else num
            except ValueError:
                pass
        return BUFFER_RADII_KM[0]

    @rx.var(cache=True)
    def age_showing_point(self) -> bool:
        return self.selected_age_radius == "Ponto" and not (
            self.multi_mode and self._multi_age_history
        )

    @rx.var(cache=True)
    def age_point_figure(self) -> go.Figure:
        import pandas as pd

        return forest_age_line_figure(pd.DataFrame(self._age_point),
                                       lang=self.language)

    @rx.var(cache=True)
    def age_histogram_figure(self) -> go.Figure:
        import pandas as pd

        df = pd.DataFrame(self._age_buffer_records())
        return forest_age_histogram_figure(df, self.age_effective_radius,
                                            lang=self.language)

    @rx.var(cache=True)
    def age_has_summary(self) -> bool:
        """Plain bool for rx.cond — a dict var is truthy in JS even when empty,
        so the summary panel needs its own gate rather than testing the dict."""
        return bool(self.age_summary_row)

    @rx.var(cache=True)
    def age_summary_row(self) -> dict[str, str]:
        """Headline numbers beside the histogram — doc/10 §5.1: median of dated
        vegetation and censored share, never a bare mean."""
        import pandas as pd

        df = pd.DataFrame(self._age_buffer_records())
        s = age_summary(df, self.age_effective_radius, lang=self.language)
        if not s:
            return {}
        median = s.get("median_dated_age")
        pt = self.language == "pt"

        def ha(value: float) -> str:
            text = f"{value:,.0f} ha"
            return text.replace(",", ".") if pt else text

        return {
            "total": ha(s["total_natural_area_ha"]),
            "censored_pct": f"{s['censored_pct']:.1f}%",
            "censored_area": ha(s["censored_area_ha"]),
            "median": (f"{median:.0f} {self.tr['years_unit']}"
                       if median is not None else "—"),
            "censored_label": s["censored_label"],
        }

    @rx.var(cache=True)
    def change_has_data(self) -> bool:
        """Gates the small loss/gain bar in the leftover space of the age
        summary column (results.py). Single-point only, like _change_stats
        itself: no multi-selection sum yet, and "Ponto" has no buffer to read."""
        return (not self.age_showing_point and not self.multi_mode
                and bool(self._change_stats))

    @rx.var(cache=True)
    def change_figure(self) -> go.Figure:
        key = f"{self.age_effective_radius:g}"
        row = self._change_stats.get(key, {})
        return change_bar_figure(row.get("loss_ha", 0.0), row.get("gain_ha", 0.0),
                                  lang=self.language)

    @rx.var(cache=True)
    def age_provenance_line(self) -> str:
        multi = self.multi_mode and self._multi_age_history
        p = self._multi_age_provenance if multi else self._age_buffers_provenance
        if self.age_showing_point:
            p = self._age_point_provenance
        if not p:
            return ""
        degraded = self.tr["provenance_degraded"] if p.get("degraded") else ""
        return (
            f"MapBiomas Desmatamento e Vegetação Secundária v3 · "
            f"{p.get('extra', {}).get('reference_year', '')} · {p.get('scale_m')} m · "
            f"{p.get('reducer')}{degraded}"
        )
