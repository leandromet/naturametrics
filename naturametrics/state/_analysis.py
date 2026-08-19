"""Land-cover history analysis: run it, hold the result, expose it to charts."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import plotly.graph_objects as go
import reflex as rx

from ..components.charts import land_cover_history_figure
from ..config.settings import BUFFER_RADII_KM
from ..services.buffers import buffer_geojson
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

    @rx.event(background=True)
    async def run_analysis(self, lat: float, lon: float):
        """Compute the land-cover history for a freshly chosen point."""
        async with self:
            self._run_token += 1
            token = self._run_token
            self.analysis_running = True
            self.analysis_error = ""
            self.has_result = False

        loop = asyncio.get_running_loop()
        try:
            p = point(lat=lat, lon=lon)
            history_task = loop.run_in_executor(
                None, land_cover_history, p, BUFFER_RADII_KM)
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
                    self.analysis_error = (
                        f"Falha ao consultar o Earth Engine: {exc}"
                    )
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
                self.analysis_error = (
                    "Nenhuma cobertura do solo encontrada neste ponto."
                )

    def set_selected_radius(self, value: str | list[str]):
        """Set the buffer whose history is charted.

        The annotation must cover the FULL union the trigger can emit
        (``str | list[str]``) — Reflex checks that the handler accepts every
        shape the component might send, and refuses to build the page otherwise.
        The segmented control sends the item label, e.g. "5 km".
        """
        raw = value[0] if isinstance(value, (list, tuple)) and value else value
        try:
            self.selected_radius = float(str(raw).replace(" km", "").strip())
        except (TypeError, ValueError):
            pass

    def toggle_normalise(self, checked: bool):
        self.normalise_chart = checked

    # ---------------------------------------------------------------------- #
    # Derived
    # ---------------------------------------------------------------------- #

    def _chart_records(self) -> list[dict[str, Any]]:
        """The rows the chart and the summary read.

        One switch, used by every derived value, so the chart, the legend and the
        provenance line can never end up describing different selections.
        """
        if self.multi_mode and self._multi_history:
            return self._multi_history
        return self._history

    @rx.var(cache=True)
    def history_figure(self) -> go.Figure:
        import pandas as pd

        df = pd.DataFrame(self._chart_records())
        return land_cover_history_figure(
            df, self.selected_radius, lang="pt", normalise=self.normalise_chart
        )

    @rx.var(cache=True)
    def radius_options(self) -> list[str]:
        return [f"{r:g} km" for r in BUFFER_RADII_KM]

    @rx.var(cache=True)
    def selected_radius_label(self) -> str:
        return f"{self.selected_radius:g} km"

    @rx.var(cache=True)
    def summary_rows(self) -> list[dict[str, str]]:
        """Top classes in the latest year, for the panel beside the chart."""
        import pandas as pd

        df = pd.DataFrame(self._chart_records())
        if df.empty or "radius_km" not in df.columns:
            return []
        sub = df[df["radius_km"] == self.selected_radius]
        if sub.empty:
            return []
        latest = sub[sub["year"] == sub["year"].max()]
        total = latest["area_ha"].sum()
        rows = latest.nlargest(6, "area_ha")
        return [
            {
                "name": str(r["class_pt"]),
                "color": str(r["color"]),
                "area": f"{r['area_ha']:,.0f} ha".replace(",", "."),
                "pct": f"{(r['area_ha'] / total * 100):.1f}%",
            }
            for _, r in rows.iterrows()
        ]

    @rx.var(cache=True)
    def provenance_line(self) -> str:
        multi = self.multi_mode and self._multi_history
        p = self._multi_provenance if multi else self._provenance
        if not p:
            return ""
        degraded = " · resultado degradado" if p.get("degraded") else ""
        # The overlap warning belongs here rather than in a tooltip: it is the
        # one thing that makes a sum over sampling units easy to misread.
        summed = (f" · soma de {len(self.multi_points)} conglomerados "
                  f"(buffers sobrepostos são contados em cada um)") if multi else ""
        return (
            f"MapBiomas {p.get('extra', {}).get('collection', '')} · "
            f"{len(p.get('bands', []))} anos · {p.get('scale_m')} m · "
            f"{p.get('reducer')}{degraded}{summed}"
        )
