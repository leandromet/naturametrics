"""Analysis state for the Canada page: run it, hold it, expose it to charts.

Three independent Earth Engine products answer three panels, and they are
deliberately given **separate error channels**: the ACI has a coverage hole that
NTEMS and Hansen do not, so a click in the boreal north must be able to leave the
land-cover panel empty while the forest panels fill in normally. Folding them
into one error would make the whole page look broken at exactly the coordinates
where two thirds of it still works.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import plotly.graph_objects as go
import reflex as rx

from ...config.settings import BUFFER_MODE_DEFAULT, BUFFER_RADII_KM
from ..components.charts import (
    aci_history_figure, forest_age_histogram_figure, loss_by_year_figure,
)
from ..config import aafc
from ..config import forest as fc_cfg
from ..services.aci_history import land_cover_history, pixel_series
from ..services.forest import (
    age_summary, buffer_forest_age, change_stats, loss_by_year, point_forest_age,
)
from ..services.geo import CoordinateError, point

logger = logging.getLogger(__name__)


class CanadaAnalysisMixin(rx.State, mixin=True):
    """Everything computed for the current study point."""

    analysis_running: bool = False
    analysis_error: str = ""
    has_result: bool = False

    age_running: bool = False
    age_error: str = ""

    selected_radius: float = BUFFER_RADII_KM[0]
    normalise_chart: bool = False

    #: Superseded-run guard. A user clicking a second point while the first is
    #: still in flight must not see the first one's answer land afterwards.
    _run_token: int = 0

    _history: list[dict[str, Any]] = []
    _provenance: dict[str, Any] = {}
    _pixel: list[dict[str, Any]] = []
    _pixel_provenance: dict[str, Any] = {}

    _age_buffers: list[dict[str, Any]] = []
    _age_provenance: dict[str, Any] = {}
    _age_point: dict[str, Any] = {}
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
            self.age_running = True
            self.age_error = ""
            radius = self.selected_radius

        loop = asyncio.get_running_loop()
        p = point(lat=lat, lon=lon)

        # --- crop inventory ------------------------------------------------
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
            logger.exception("Canada ACI analysis failed")
            async with self:
                if token == self._run_token:
                    self.analysis_running = False
                    self.analysis_error = self.tr["err_earth_engine_query"].format(exc=exc)
            return

        async with self:
            if token != self._run_token:
                logger.info("Discarding superseded Canada analysis for %s", p)
                return
            self._history = df.to_dict("records")
            self._provenance = prov.to_dict()
            self._pixel = px_df.to_dict("records")
            self._pixel_provenance = px_prov.to_dict()
            self.analysis_running = False
            self.has_result = True
            # Deliberately NOT an error when empty — north of the ACI extent the
            # panel shows its own explanatory empty state instead.

        # --- forest age + change ------------------------------------------
        # Separate try/except on purpose: the ACI answer above is already on
        # screen, and a Hansen or NTEMS hiccup must not blank it.
        try:
            age_task = loop.run_in_executor(
                None, buffer_forest_age, p, BUFFER_RADII_KM, BUFFER_MODE_DEFAULT)
            pt_age_task = loop.run_in_executor(None, point_forest_age, p)
            change_task = loop.run_in_executor(
                None, change_stats, p, BUFFER_RADII_KM, BUFFER_MODE_DEFAULT)
            loss_task = loop.run_in_executor(None, loss_by_year, p, radius)
            (age_df, age_prov), (pt_age, _), (chg, chg_prov), (loss_df, _) = \
                await asyncio.gather(age_task, pt_age_task, change_task, loss_task)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Canada forest analysis failed")
            async with self:
                if token == self._run_token:
                    self.age_running = False
                    self.age_error = self.tr["err_forest_failed"].format(exc=exc)
            return

        async with self:
            if token != self._run_token:
                return
            self._age_buffers = age_df.to_dict("records")
            self._age_provenance = age_prov.to_dict()
            self._age_point = pt_age
            self._change_stats = chg
            self._change_provenance = chg_prov.to_dict()
            self._loss_series = loss_df.to_dict("records")
            self.age_running = False

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
            logger.warning("Canada change re-run failed: %s", exc)
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
    # Derived — crop inventory
    # ---------------------------------------------------------------------- #

    @rx.var(cache=True)
    def aci_has_data(self) -> bool:
        """Whether the land-cover panel has anything at all to draw.

        Distinct from ``has_result``: north of the ACI extent the analysis
        succeeds and this stays False, which is what selects the explanatory
        empty state instead of the chart.
        """
        return bool(self._history)

    @rx.var(cache=True)
    def history_figure(self) -> go.Figure:
        import pandas as pd
        return aci_history_figure(
            pd.DataFrame(self._history), self.selected_radius,
            lang=self.language, normalise=self.normalise_chart)

    @rx.var(cache=True)
    def radius_options(self) -> list[str]:
        return [f"{r:g} km" for r in BUFFER_RADII_KM]

    @rx.var(cache=True)
    def selected_radius_label(self) -> str:
        return f"{self.selected_radius:g} km"

    @rx.var(cache=True)
    def latest_aci_year(self) -> int:
        """The most recent year actually present, which is not always 2025."""
        years = [int(r["year"]) for r in self._history] if self._history else []
        return max(years) if years else aafc.ACI_YEAR_END

    @rx.var(cache=True)
    def top_classes_title(self) -> str:
        """Formatted here, not in the component.

        ``self.tr[...]`` is a real dict inside a state method but a runtime Var
        in the component tree, where ``.format()`` cannot run — it would render
        the literal ``{year}``. The year is dynamic (it is the latest year the
        buffer actually has, not a constant), so this has to be a computed var
        rather than the build-time ``rx.cond`` trick used for fixed values.
        """
        return self.tr["top_classes_title"].format(year=self.latest_aci_year)

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
        return (f"AAFC Annual Crop Inventory · {len(p.get('bands', []))} "
                f"{'anos' if self.language == 'pt' else 'years'} · "
                f"{p.get('scale_m')} m · {p.get('reducer')}")

    # ---------------------------------------------------------------------- #
    # Derived — forest age
    # ---------------------------------------------------------------------- #

    @rx.var(cache=True)
    def age_has_result(self) -> bool:
        return bool(self._age_buffers)

    @rx.var(cache=True)
    def age_histogram_figure(self) -> go.Figure:
        import pandas as pd
        return forest_age_histogram_figure(
            pd.DataFrame(self._age_buffers), self.selected_radius, lang=self.language)

    @rx.var(cache=True)
    def age_summary_row(self) -> dict[str, str]:
        import pandas as pd

        s = age_summary(pd.DataFrame(self._age_buffers), self.selected_radius,
                        self._age_provenance.get("extra", {}))
        if not s:
            return {}
        pt = self.language == "pt"

        def ha(v: float) -> str:
            text = f"{v:,.0f} ha"
            return text.replace(",", ".") if pt else text

        return {
            "forest_area": ha(s["forest_area_ha"]),
            "median_bin": s.get("median_bin") or "—",
            "forest_pct": f"{s['forest_pct']:.1f}%",
            "non_forest": ha(s["non_forest_ha"]),
        }

    @rx.var(cache=True)
    def age_has_summary(self) -> bool:
        return bool(self.age_summary_row)

    @rx.var(cache=True)
    def age_point_label(self) -> str:
        """Stand age at the clicked pixel, or the not-forest message."""
        pa = self._age_point
        if not pa:
            return ""
        if not pa.get("is_forest"):
            return self.tr["age_point_not_forest"]
        return f"{pa['age']} {self.tr['age_years_unit']}"

    @rx.var(cache=True)
    def age_reference_note(self) -> str:
        return self.tr["age_reference_note"].format(
            year=fc_cfg.NTEMS_AGE_REFERENCE_YEAR)

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

        return [
            {"label": self.tr["change_loss_ha"], "value": ha(row.get("loss_ha", 0)),
             "color": fc_cfg.HANSEN_LOSS_COLOR},
            {"label": self.tr["change_gain_ha"], "value": ha(row.get("gain_ha", 0)),
             "color": fc_cfg.HANSEN_GAIN_COLOR},
            {"label": self.tr["change_forest2000_ha"],
             "value": ha(row.get("forest2000_ha", 0)),
             "color": fc_cfg.HANSEN_FOREST_COLOR},
        ]

    @rx.var(cache=True)
    def loss_figure(self) -> go.Figure:
        import pandas as pd
        return loss_by_year_figure(pd.DataFrame(self._loss_series), lang=self.language)
