"""Downloads: what goes in the file, and what it costs to build.

Two independent exports, matching the two things on screen:

* **the study point** — always cheap, because every number in it was already
  computed to draw the chart. Nothing is recomputed, so the file and the screen
  cannot disagree (doc/11 §5).
* **the conglomerado selection** — driven by the same four filters as the map,
  so "what will I get" is answerable by looking at the layer panel.

The checklist matters because the three parts have wildly different costs: the
point list is free, the single-pixel series is one streamed Earth Engine
download at any size, and the buffer histories are a fan-out that takes about
0.11 s per conglomerado. The panel says which is which rather than letting the
user discover it by waiting.

⚠️ ``rx.download`` carries the bytes to the browser inside the event payload, so
a file costs roughly 4/3 of its size on the WebSocket. That is fine at the sizes
the cap allows (~14 MB at 1 500 conglomerados) and is the reason the cap is not
simply raised: past this scale the delivery, not the computation, becomes the
problem, and the answer there is a background job writing to storage.
"""

from __future__ import annotations

import asyncio
import logging

import reflex as rx

from ..config.settings import BUFFER_RADII_KM, EXPORT_MAX_BUFFER_POINTS
from ..services import exports, ifn
from ..services.ods import MIMETYPE
from ._proxy import plain

logger = logging.getLogger(__name__)


class ExportMixin(rx.State, mixin=True):
    """The export panel."""

    export_open: bool = False

    #: "filtros" | "manual" — which way the selection is named. Kept explicit
    #: rather than inferred from "is the manual selection non-empty", so that
    #: leaving a few clicked points behind cannot silently change what a filter
    #: export contains.
    export_source: str = "filtros"

    # --- what to include in the selection export --------------------------
    exp_points: bool = True
    exp_pixel: bool = True
    exp_buffers: bool = False
    #: "" means every radius; otherwise the one radius asked for, as a string
    #: so it can drive a select directly.
    exp_radius: str = ""

    # --- progress ---------------------------------------------------------
    export_busy: bool = False
    export_stage: str = ""
    export_done: int = 0
    export_total: int = 0
    export_error: str = ""
    export_result: str = ""

    def set_export_open(self, value: bool):
        self.export_open = value
        if value:
            # Stale success or failure text from a previous run would read as
            # the status of the run the user is about to start.
            self.export_error = ""
            self.export_result = ""

    def set_export_source(self, value: str | list[str]):
        raw = value[0] if isinstance(value, (list, tuple)) and value else value
        self.export_source = "manual" if str(raw).startswith("Seleção manual") \
            else "filtros"

    def toggle_exp_points(self, checked: bool):
        self.exp_points = checked

    def toggle_exp_pixel(self, checked: bool):
        self.exp_pixel = checked

    def toggle_exp_buffers(self, checked: bool):
        self.exp_buffers = checked

    def set_exp_radius(self, value: str | list[str]):
        raw = value[0] if isinstance(value, (list, tuple)) and value else value
        label = str(raw)
        self.exp_radius = "" if label.startswith("Todos") else \
            label.replace(" km", "").strip()

    def _radii(self) -> tuple[float, ...]:
        if not self.exp_radius:
            return tuple(sorted(BUFFER_RADII_KM))
        try:
            return (float(self.exp_radius),)
        except ValueError:
            return tuple(sorted(BUFFER_RADII_KM))

    # ---------------------------------------------------------------------- #
    # Derived
    # ---------------------------------------------------------------------- #

    def _spec(self) -> exports.SelectionSpec:
        """The export request, assembled from the panel and the map."""
        manual = self.export_source == "manual"
        return exports.SelectionSpec(
            region=self.ifn_region, uf=self.ifn_uf,
            municipality=self.ifn_municipality, biome=self.ifn_biome,
            conglomerados=plain(self.multi_conglomerados) if manual else None,
            radii=self._radii(),
            include_points=self.exp_points, include_pixel=self.exp_pixel,
            include_buffers=self.exp_buffers,
        )

    @rx.var
    def export_source_options(self) -> list[str]:
        return ["Filtros do mapa", f"Seleção manual ({self.multi_count})"]

    @rx.var
    def export_source_value(self) -> str:
        return (f"Seleção manual ({self.multi_count})"
                if self.export_source == "manual" else "Filtros do mapa")

    @rx.var
    def export_manual_available(self) -> bool:
        return self.multi_count > 0

    @rx.var
    def export_selection_count(self) -> int:
        if self.export_source == "manual":
            return self.multi_count
        return ifn.count(self.ifn_region, self.ifn_uf, self.ifn_municipality,
                         self.ifn_biome)

    @rx.var
    def export_selection_label(self) -> str:
        if self.export_source == "manual":
            return f"{self.multi_count} conglomerados escolhidos no mapa"
        parts = [p for p in (self.ifn_region, self.ifn_biome, self.ifn_uf,
                             self.ifn_municipality) if p]
        return " · ".join(parts) if parts else "Brasil inteiro (sem filtro)"

    @rx.var
    def export_count_label(self) -> str:
        n = self.export_selection_count
        return f"{n:,} conglomerado".replace(",", ".") + ("" if n == 1 else "s")

    @rx.var
    def export_radius_options(self) -> list[str]:
        return ["Todos os raios"] + [f"{r:g} km" for r in sorted(BUFFER_RADII_KM)]

    @rx.var
    def export_radius_value(self) -> str:
        return f"{float(self.exp_radius):g} km" if self.exp_radius \
            else "Todos os raios"

    @rx.var
    def export_buffer_note(self) -> str:
        """What the buffer export will cost. Advisory — nothing is refused."""
        n = self.export_selection_count
        if n == 0:
            return "Nenhum conglomerado na seleção atual."
        return exports.buffer_estimate_message(n, self._radii())

    @rx.var
    def export_buffer_heavy(self) -> bool:
        """Big enough that the *download* is the risk, not the computation."""
        n = self.export_selection_count
        return bool(n) and exports.buffer_estimate(n, self._radii())["heavy"]

    @rx.var
    def export_buffer_over_limit(self) -> bool:
        """The one refusal: past the largest-biome ceiling."""
        n = self.export_selection_count
        return bool(n) and exports.buffer_estimate(n, self._radii())["over_limit"]

    @rx.var
    def export_progress_label(self) -> str:
        if not self.export_busy:
            return ""
        if self.export_total:
            return f"{self.export_stage} — {self.export_done}/{self.export_total}"
        return self.export_stage

    @rx.var
    def export_nothing_selected(self) -> bool:
        return not (self.exp_points or self.exp_pixel or self.exp_buffers)

    # ---------------------------------------------------------------------- #
    # Study point
    # ---------------------------------------------------------------------- #

    @rx.event(background=True)
    async def download_study_point(self):
        """One spreadsheet for the location on screen. No Earth Engine calls."""
        async with self:
            if not self.has_result:
                self.export_error = "Escolha um ponto no mapa primeiro."
                return
            self.export_busy = True
            self.export_stage = "Montando a planilha do ponto"
            self.export_error = ""
            self.export_result = ""
            history, prov = plain(self._history), plain(self._provenance)
            pixel, pixel_prov = plain(self._pixel), plain(self._pixel_provenance)
            lat, lon = self.study_lat, self.study_lon
            identity = {
                "source": self.point_source,
                "conglomerado": self.point_conglomerado,
                "uf": self.point_uf,
                "municipio": self.point_municipio,
                "bioma": self.point_bioma,
            }

        loop = asyncio.get_running_loop()
        try:
            data, name = await loop.run_in_executor(
                None, _build_study_point, lat, lon, history, prov, pixel,
                pixel_prov, identity)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Study-point export failed")
            async with self:
                self.export_busy = False
                self.export_error = f"Falha ao gerar a planilha: {exc}"
            return

        async with self:
            self.export_busy = False
            self.export_stage = ""
            self.export_result = f"{name} ({len(data) // 1024} KiB)"
        return rx.download(data=data, filename=name, mime_type=MIMETYPE)

    # ---------------------------------------------------------------------- #
    # Conglomerado selection
    # ---------------------------------------------------------------------- #

    @rx.event(background=True)
    async def download_selection(self):
        """One spreadsheet covering every conglomerado the filters select."""
        async with self:
            spec = self._spec()
            if self.export_nothing_selected:
                self.export_error = "Marque pelo menos um conjunto de dados."
                return
            self.export_busy = True
            self.export_error = ""
            self.export_result = ""
            self.export_done = 0
            self.export_total = 0
            self.export_stage = "Reunindo os conglomerados"

        if spec.include_buffers and len(spec.points()) > EXPORT_MAX_BUFFER_POINTS:
            async with self:
                self.export_busy = False
                self.export_error = exports.buffer_estimate_message(
                    len(spec.points()), spec.radii)
            return

        points = spec.points()
        if not points:
            async with self:
                self.export_busy = False
                self.export_error = "Nenhum conglomerado na seleção atual."
            return

        loop = asyncio.get_running_loop()
        pixel = buffers = None

        try:
            if spec.include_pixel:
                async with self:
                    self.export_stage = "Lendo o pixel de cada conglomerado"
                pixel = await loop.run_in_executor(
                    None, exports.selection_pixel_frame, spec)

            if spec.include_buffers:
                async with self:
                    self.export_stage = "Calculando os buffers"
                    self.export_total = len(points)

                # The callback runs on Earth Engine worker threads, so it cannot
                # touch state directly; it drops the counter somewhere the async
                # side can read, and the async side publishes it.
                counter = {"done": 0}

                def progress(done: int, total: int) -> None:
                    counter["done"] = done

                task = loop.run_in_executor(
                    None, exports.selection_buffer_frame, spec, points, progress)
                while not task.done():
                    await asyncio.sleep(0.5)
                    async with self:
                        self.export_done = counter["done"]
                buffers = await task

            async with self:
                self.export_stage = "Montando a planilha"
            data, name = await loop.run_in_executor(
                None, exports.selection_workbook, spec, points, pixel, buffers)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Selection export failed")
            async with self:
                self.export_busy = False
                self.export_stage = ""
                self.export_error = f"Falha ao gerar a planilha: {exc}"
            return

        async with self:
            self.export_busy = False
            self.export_stage = ""
            self.export_done = self.export_total
            failed = buffers[2] if buffers else []
            note = f" · {len(failed)} conglomerado(s) falharam" if failed else ""
            self.export_result = f"{name} ({len(data) // 1024} KiB){note}"
        return rx.download(data=data, filename=name, mime_type=MIMETYPE)


def _build_study_point(lat, lon, history, prov, pixel, pixel_prov, identity):
    """Rebuild the frames and write the workbook, off the event loop."""
    import pandas as pd

    from ..services.geo import point
    from ..services.provenance import Provenance

    def revive(d: dict) -> Provenance:
        # State stores provenance as a plain dict so it can be serialised; the
        # workbook wants the dataclass back. Round-tripping through the class is
        # what keeps the two from drifting into different shapes.
        return Provenance(**d)

    return exports.study_point_workbook(
        point(lat=lat, lon=lon),
        pd.DataFrame(history), revive(prov),
        pd.DataFrame(pixel), revive(pixel_prov),
        identity=identity,
    )
