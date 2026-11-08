"""Analysis state for the USA page: run it, hold it, expose it to charts.

Two independent Earth Engine products answer two panels (GLC-FCS30D land cover and
Hansen forest change), each with its **own error channel**: a Hansen hiccup must not
blank a land-cover answer that is already on screen.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import plotly.graph_objects as go
import reflex as rx

from ...config.settings import BUFFER_MODE_DEFAULT, BUFFER_RADII_KM
from ..components.charts import (
    age_histogram_figure, canopy_figure, class_history_figure, glc_history_figure, loss_by_year_figure,
)
from ..config import glc
from ..config import disturbance as dist_cfg
from ..config import forest as fc_cfg
from ..services.glc_history import land_cover_history, pixel_series
from ..services import disturbance as dist_service
from ..services.forest import change_stats, loss_by_year
from ..services.geo import CoordinateError, point

logger = logging.getLogger(__name__)


class WorldAnalysisMixin(rx.State, mixin=True):
    """Everything computed for the current study point."""

    analysis_running: bool = False
    analysis_error: str = ""
    has_result: bool = False

    forest_running: bool = False
    forest_error: str = ""

    dist_running: bool = False
    dist_error: str = ""
    age_running: bool = False
    age_error: str = ""
    fire_running: bool = False
    fire_error: str = ""
    canopy_running: bool = False
    canopy_error: str = ""

    selected_radius: float = BUFFER_RADII_KM[0]
    normalise_chart: bool = False

    #: Superseded-run guard. A user clicking a second point while the first is
    #: still in flight must not see the first one's answer land afterwards.
    _run_token: int = 0

    _history: list[dict[str, Any]] = []
    _provenance: dict[str, Any] = {}
    _pixel: list[dict[str, Any]] = []
    _pixel_provenance: dict[str, Any] = {}

    _dist: list[dict[str, Any]] = []
    _dist_provenance: dict[str, Any] = {}
    _age: list[dict[str, Any]] = []
    _age_provenance: dict[str, Any] = {}
    _fire: list[dict[str, Any]] = []
    _fire_provenance: dict[str, Any] = {}
    _canopy: list[dict[str, Any]] = []
    _canopy_provenance: dict[str, Any] = {}
    _change_stats: dict[str, Any] = {}
    _change_provenance: dict[str, Any] = {}
    _loss_series: list[dict[str, Any]] = []

    # ---------------------------------------------------------------------- #
    # Running
    # ---------------------------------------------------------------------- #

    @rx.event(background=True)
    async def run_analysis(self, lat: float, lon: float):
        """Compute everything for a freshly chosen point."""
        async with self:
            self._run_token += 1
            token = self._run_token
            self.analysis_running = True
            self.analysis_error = ""
            self.forest_running = True
            self.forest_error = ""
            radius = self.selected_radius

        loop = asyncio.get_running_loop()
        p = point(lat=lat, lon=lon)

        # --- land cover ------------------------------------------------
        try:
            hist_task = loop.run_in_executor(
                None, land_cover_history, p, BUFFER_RADII_KM, BUFFER_MODE_DEFAULT)
            pixel_task = loop.run_in_executor(None, pixel_series, p)
            (df, prov), (px_df, px_prov) = await asyncio.gather(hist_task, pixel_task)
        except CoordinateError as exc:
            async with self:
                if token == self._run_token:
                    self.analysis_running = False
                    self.analysis_error = str(exc)
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("USA GLC analysis failed")
            async with self:
                if token == self._run_token:
                    self.analysis_running = False
                    self.analysis_error = self.tr["err_earth_engine_query"].format(exc=exc)
            return

        async with self:
            if token != self._run_token:
                logger.info("Discarding superseded USA analysis for %s", p)
                return
            self._history = df.to_dict("records")
            self._provenance = prov.to_dict()
            self._pixel = px_df.to_dict("records")
            self._pixel_provenance = px_prov.to_dict()
            self.analysis_running = False
            self.has_result = True

        # --- forest change -------------------------------------------------
        # Separate try/except on purpose: the land-cover answer above is already on
        # screen, and a Hansen hiccup must not blank it.
        try:
            change_task = loop.run_in_executor(
                None, change_stats, p, BUFFER_RADII_KM, BUFFER_MODE_DEFAULT)
            loss_task = loop.run_in_executor(None, loss_by_year, p, radius)
            (chg, chg_prov), (loss_df, _) = await asyncio.gather(change_task, loss_task)
        except Exception as exc:  # noqa: BLE001
            logger.exception("USA forest analysis failed")
            async with self:
                if token == self._run_token:
                    self.forest_running = False
                    self.forest_error = self.tr["err_forest_failed"].format(exc=exc)
            return

        async with self:
            if token != self._run_token:
                return
            self._change_stats = chg
            self._change_provenance = chg_prov.to_dict()
            self._loss_series = loss_df.to_dict("records")
            self.forest_running = False

    @rx.event(background=True)
    async def run_extras(self, lat: float, lon: float):
        """LCMS disturbance and time-since-disturbance, MTBS fire and tree canopy — four
        independent answers, each with its own error channel, run together."""
        async with self:
            token = self._run_token
            self.dist_running = self.age_running = self.fire_running = self.canopy_running = True
            self.dist_error = self.age_error = self.fire_error = self.canopy_error = ""
        loop = asyncio.get_running_loop()
        p = point(lat=lat, lon=lon)
        jobs = {
            "dist": dist_service.disturbance_history, "age": dist_service.time_since_disturbance,
            "fire": dist_service.fire_history, "canopy": dist_service.canopy_history,
        }

        async def one(name, fn):
            try:
                df, prov = await loop.run_in_executor(None, fn, p, BUFFER_RADII_KM, BUFFER_MODE_DEFAULT)
            except Exception as exc:  # noqa: BLE001
                logger.exception("USA %s analysis failed", name)
                async with self:
                    if token == self._run_token:
                        setattr(self, f"{name}_running", False)
                        setattr(self, f"{name}_error", self.tr["err_extra_failed"].format(exc=exc))
                return
            async with self:
                if token != self._run_token:
                    return
                setattr(self, f"_{name}", df.to_dict("records"))
                setattr(self, f"_{name}_provenance", prov.to_dict())
                setattr(self, f"{name}_running", False)

        await asyncio.gather(*(one(n, f) for n, f in jobs.items()))

    @rx.event(background=True)
    async def run_change_only(self, lat: float, lon: float):
        """Re-run just the Hansen numbers after the forest threshold moved."""
        async with self:
            token = self._run_token
            radius, threshold = self.selected_radius, self.treecover_threshold

        loop = asyncio.get_running_loop()
        p = point(lat=lat, lon=lon)
        try:
            chg_task = loop.run_in_executor(
                None, change_stats, p, BUFFER_RADII_KM, BUFFER_MODE_DEFAULT, threshold)
            loss_task = loop.run_in_executor(
                None, loss_by_year, p, radius, BUFFER_MODE_DEFAULT, threshold)
            (chg, chg_prov), (loss_df, _) = await asyncio.gather(chg_task, loss_task)
        except Exception as exc:  # noqa: BLE001
            logger.warning("USA change re-run failed: %s", exc)
            return

        async with self:
            if token != self._run_token:
                return
            self._change_stats = chg
            self._change_provenance = chg_prov.to_dict()
            self._loss_series = loss_df.to_dict("records")

    def set_selected_radius(self, value: str | list[str]):
        raw = value[0] if isinstance(value, (list, tuple)) and value else value
        try:
            self.selected_radius = float(str(raw).replace(" km", "").strip())
        except ValueError:
            return
        if self.has_point:
            return type(self).run_change_only(self.study_lat, self.study_lon)

    def toggle_normalise(self, checked: bool):
        self.normalise_chart = checked

    # ---------------------------------------------------------------------- #
    # Derived — land cover
    # ---------------------------------------------------------------------- #

    @rx.var(cache=True)
    def glc_has_data(self) -> bool:
        """Whether the land-cover panel has anything to draw."""
        return bool(self._history)

    @rx.var(cache=True)
    def history_figure(self) -> go.Figure:
        import pandas as pd
        return glc_history_figure(
            pd.DataFrame(self._history), self.selected_radius,
            lang=self.language, normalise=self.normalise_chart)

    @rx.var(cache=True)
    def radius_options(self) -> list[str]:
        return [f"{r:g} km" for r in BUFFER_RADII_KM]

    @rx.var(cache=True)
    def selected_radius_label(self) -> str:
        return f"{self.selected_radius:g} km"

    @rx.var(cache=True)
    def latest_glc_year(self) -> int:
        """The most recent year actually present, which is not always 2025."""
        years = [int(r["year"]) for r in self._history] if self._history else []
        return max(years) if years else glc.GLC_YEAR_END

    @rx.var(cache=True)
    def top_classes_title(self) -> str:
        """Formatted here, not in the component.

        ``self.tr[...]`` is a real dict inside a state method but a runtime Var
        in the component tree, where ``.format()`` cannot run — it would render
        the literal ``{year}``. The year is dynamic (it is the latest year the
        buffer actually has, not a constant), so this has to be a computed var
        rather than the build-time ``rx.cond`` trick used for fixed values.
        """
        return self.tr["top_classes_title"].format(year=self.latest_glc_year)

    @rx.var(cache=True)
    def summary_rows(self) -> list[dict[str, str]]:
        """Top classes in the latest year, for the panel beside the chart."""
        import pandas as pd

        df = pd.DataFrame(self._history)
        if df.empty or "radius_km" not in df.columns:
            return []
        sub = df[df["radius_km"] == self.selected_radius]
        if sub.empty:
            return []
        latest = sub[sub["year"] == sub["year"].max()]
        total = latest["area_ha"].sum()
        if total <= 0:
            return []
        pt = self.language == "pt"
        col = "class_pt" if pt else "class_en"
        return [
            {
                "name": str(r[col]),
                "color": str(r["color"]),
                "area": (f"{r['area_ha']:,.0f} ha".replace(",", ".") if pt
                         else f"{r['area_ha']:,.0f} ha"),
                "pct": f"{(r['area_ha'] / total * 100):.1f}%",
            }
            for _, r in latest.nlargest(6, "area_ha").iterrows()
        ]

    @rx.var(cache=True)
    def provenance_line(self) -> str:
        p = self._provenance
        if not p:
            return ""
        return (f"GLC-FCS30D · {len(p.get('bands', []))} "
                f"{'anos' if self.language == 'pt' else 'years'} · "
                f"{p.get('scale_m')} m · {p.get('reducer')}")

    # ---------------------------------------------------------------------- #
    # Derived — disturbance, time since disturbance, fire, canopy
    # ---------------------------------------------------------------------- #
    @rx.var(cache=True)
    def dist_has_data(self) -> bool:
        return bool(self._dist)

    @rx.var(cache=True)
    def dist_figure(self) -> go.Figure:
        import pandas as pd
        return class_history_figure(pd.DataFrame(self._dist), self.selected_radius, lang=self.language)

    @rx.var(cache=True)
    def age_has_data(self) -> bool:
        return bool(self._age)

    @rx.var(cache=True)
    def age_figure(self) -> go.Figure:
        import pandas as pd
        return age_histogram_figure(pd.DataFrame(self._age), self.selected_radius, lang=self.language)

    @rx.var(cache=True)
    def age_summary_rows(self) -> list[dict[str, str]]:
        """Tree area, share of the buffer, and the censored share — beside the histogram."""
        import math
        import pandas as pd
        df = pd.DataFrame(self._age)
        if df.empty:
            return []
        sub = df[df["radius_km"] == self.selected_radius]
        if sub.empty:
            return []
        pt = self.language == "pt"
        total = float(sub["area_ha"].sum())
        censored = float(sub.loc[sub["bin"] == dist_cfg.AGE_CENSORED, "area_ha"].sum())
        disc = math.pi * (self.selected_radius * 100.0) ** 2     # ha in a disc of r km
        ha = lambda v: (f"{v:,.0f} ha".replace(",", ".") if pt else f"{v:,.0f} ha")
        return [
            {"label": self.tr["age_tree_area"], "value": ha(total)},
            {"label": self.tr["age_tree_share"], "value": f"{min(100.0, total / disc * 100):.0f}%"},
            {"label": self.tr["age_censored_share"], "value": f"{(censored / total * 100) if total else 0:.0f}%"},
        ]

    @rx.var(cache=True)
    def fire_has_data(self) -> bool:
        return bool(self._fire)

    @rx.var(cache=True)
    def fire_figure(self) -> go.Figure:
        import pandas as pd
        return class_history_figure(pd.DataFrame(self._fire), self.selected_radius, lang=self.language,
                                    stack_order=[5, 1, 2, 3, 4])

    @rx.var(cache=True)
    def fire_empty_note(self) -> bool:
        """MTBS answered but mapped no fire here — worth saying, since MTBS misses small fires."""
        return bool(self._fire_provenance) and not self._fire and not self.fire_running \
            and not self.fire_error

    @rx.var(cache=True)
    def canopy_has_data(self) -> bool:
        return bool(self._canopy)

    @rx.var(cache=True)
    def canopy_figure(self) -> go.Figure:
        import pandas as pd
        return canopy_figure(pd.DataFrame(self._canopy), lang=self.language)

    # ---------------------------------------------------------------------- #
    # Derived — forest change
    # ---------------------------------------------------------------------- #

    @rx.var(cache=True)
    def change_has_data(self) -> bool:
        return bool(self._change_stats)

    @rx.var(cache=True)
    def change_title(self) -> str:
        return self.tr["change_title"].format(
            first=fc_cfg.HANSEN_LOSS_YEAR_START, last=fc_cfg.HANSEN_LOSS_YEAR_END)

    @rx.var(cache=True)
    def change_rows(self) -> list[dict[str, str]]:
        row = self._change_stats.get(f"{self.selected_radius:g}", {})
        if not row:
            return []
        pt = self.language == "pt"

        def ha(v: float) -> str:
            text = f"{float(v):,.0f} ha"
            return text.replace(",", ".") if pt else text

        loss = float(row.get("loss_ha", 0) or 0)
        gain = float(row.get("gain_ha", 0) or 0)
        # Net is taken over 2001–2012, the only window both bands cover. Netting
        # gain against the full 2001–2025 loss would subtract a 13-year figure
        # from a 25-year one and present the difference as a balance.
        loss_window = float(row.get("loss_gain_window_ha", 0) or 0)
        net = gain - loss_window
        net_text = ("+" if net > 0 else "") + ha(net)
        return [
            {"label": self.tr["change_loss_ha"], "value": ha(loss),
             "color": fc_cfg.HANSEN_LOSS_COLOR},
            {"label": self.tr["change_gain_ha"], "value": ha(gain),
             "color": fc_cfg.HANSEN_GAIN_COLOR},
            {"label": self.tr["change_net_ha"], "value": net_text,
             "color": (fc_cfg.HANSEN_GAIN_COLOR if net > 0
                       else fc_cfg.HANSEN_LOSS_COLOR)},
            {"label": self.tr["change_forest2000_ha"],
             "value": ha(float(row.get("forest2000_ha", 0) or 0)),
             "color": fc_cfg.HANSEN_FOREST_COLOR},
        ]

    @rx.var(cache=True)
    def loss_figure(self) -> go.Figure:
        import pandas as pd

        row = self._change_stats.get(f"{self.selected_radius:g}", {})
        return loss_by_year_figure(
            pd.DataFrame(self._loss_series),
            gain_total_ha=float(row.get("gain_ha") or 0.0),
            lang=self.language,
        )


    # ---------------------------------------------------------------------- #
    # Landscape metrics and biomass (the Brazil page's tabs, on this country's data)
    # ---------------------------------------------------------------------- #
    metrics_running: bool = False
    metrics_error: str = ""
    biomass_running: bool = False
    biomass_error: str = ""
    _metrics: list[dict[str, Any]] = []
    _metrics_provenance: dict[str, Any] = {}
    _biomass: list[dict[str, Any]] = []
    _biomass_provenance: dict[str, Any] = {}

    @rx.event(background=True)
    async def run_landscape_biomass(self, lat: float, lon: float):
        """Landscape metrics on the latest land-cover year, and biomass by year. Two independent
        answers with their own error channels, so one failing never blanks the other."""
        from ..services import extras as xs

        async with self:
            token = self._run_token
            self.metrics_running = self.biomass_running = True
            self.metrics_error = self.biomass_error = ""
        loop = asyncio.get_running_loop()
        p = point(lat=lat, lon=lon)

        async def metrics():
            try:
                summary, _hist, prov = await loop.run_in_executor(None, xs.landscape_for_point, p, BUFFER_RADII_KM)
            except Exception as exc:  # noqa: BLE001
                logger.exception("landscape metrics failed")
                async with self:
                    if token == self._run_token:
                        self.metrics_running = False
                        self.metrics_error = self.tr["err_extra_failed"].format(exc=exc)
                return
            async with self:
                if token != self._run_token:
                    return
                self._metrics = summary.to_dict("records") if summary is not None and not summary.empty else []
                self._metrics_provenance = prov.to_dict() if prov is not None else {}
                self.metrics_running = False

        async def biomass():
            try:
                df, prov = await loop.run_in_executor(None, xs.biomass_for_point, p, BUFFER_RADII_KM)
            except Exception as exc:  # noqa: BLE001
                logger.exception("biomass failed")
                async with self:
                    if token == self._run_token:
                        self.biomass_running = False
                        self.biomass_error = self.tr["err_extra_failed"].format(exc=exc)
                return
            async with self:
                if token != self._run_token:
                    return
                self._biomass = df.to_dict("records") if not df.empty else []
                self._biomass_provenance = prov.to_dict()
                self.biomass_running = False

        await asyncio.gather(metrics(), biomass())

    @rx.var(cache=True)
    def metrics_has(self) -> bool:
        return bool(self._metrics)

    @rx.var(cache=True)
    def metrics_rows(self) -> list[dict[str, str]]:
        import math
        pt = self.language == "pt"

        def f(v, d=0):
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return "—"
            text = f"{float(v):,.{d}f}"
            return text.replace(",", "X").replace(".", ",").replace("X", ".") if pt else text

        return [{"radius": f"{float(r['radius_km']):g} km", "patches": f(r["patches"]),
                 "largest": f(r["largest_patch_pct"], 1), "edge": f(r["edge_density"], 1),
                 "meff": f(r["meff_ha"]), "shannon": f(r["shannon"], 2),
                 "evenness": f(r["simpson_evenness"], 2)} for r in self._metrics]

    @rx.var(cache=True, deps=["biomass_running", "selected_radius", "language"], auto_deps=False)
    def biomass_has(self) -> bool:
        return bool(self._biomass)

    @rx.var(cache=True, deps=["biomass_running", "selected_radius", "language"], auto_deps=False)
    def biomass_rows(self) -> list[dict[str, str]]:
        import math
        pt = self.language == "pt"
        rows = [r for r in self._biomass if float(r["radius_km"]) == float(self.selected_radius)]

        def f(v, d=1):
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return "—"
            text = f"{float(v):,.{d}f}"
            return text.replace(",", "X").replace(".", ",").replace("X", ".") if pt else text

        return [{"year": str(int(r["year"])), "mean": f(r["agb_mean_mgha"]), "sd": f(r["agb_sd_mgha"])}
                for r in sorted(rows, key=lambda r: r["year"])]

    @rx.var(cache=True, deps=["biomass_running", "selected_radius", "language"], auto_deps=False)
    def biomass_chart_figure(self) -> go.Figure:
        import pandas as pd
        from ..components.charts import biomass_chart
        return biomass_chart(pd.DataFrame(self._biomass), self.selected_radius, lang=self.language)
