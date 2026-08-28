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
from ..services import abuse_control, exports, ifn
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

    # --- the study-point "paper-friendly" HTML report (services.report) --
    # A third export path alongside the ODS above and the per-chart/per-
    # table icons in components/results.py — see services/report.py's own
    # docstring for why these are complementary, not redundant. Both default
    # off: the ODS button above stays the one-click default action, and nothing
    # about it changes just because these two exist.
    exp_report_figures: bool = False
    exp_report_tables: bool = False

    # --- what to include in the selection export --------------------------
    exp_points: bool = True
    exp_pixel: bool = True
    exp_buffers: bool = False
    #: The nearest-neighbour fragment distance (services.connectivity) — its
    #: own checkbox, not folded into exp_buffers: a second, pricier Earth
    #: Engine call plus a local geometry search per point, same reasoning as
    #: services.exports.SelectionSpec.include_connectivity.
    exp_connectivity: bool = False
    #: "" means every radius; otherwise the one radius asked for, as a string
    #: so it can drive a select directly.
    exp_radius: str = ""
    #: Bounding-box tables (services.exports.selection_full_area_frame),
    #: alongside the per-conglomerado ones above. Only offered for a manual
    #: selection — see export_source.
    exp_full_area: bool = False

    # --- progress ---------------------------------------------------------
    export_busy: bool = False
    export_stage: str = ""
    export_done: int = 0
    export_total: int = 0
    export_error: str = ""
    export_result: str = ""

    #: The friction step (doc: security audit, "public access safety") — the
    #: buffer/age/change fan-out is the one part of this app that costs real
    #: Earth Engine compute per click, so the first click on it asks rather
    #: than runs. Reset wherever the request it would confirm might have
    #: changed, so a stale "are you sure" can never wave through a different
    #: export than the one the user actually looked at.
    export_confirm_pending: bool = False

    def set_export_open(self, value: bool):
        self.export_open = value
        if value:
            # Stale success or failure text from a previous run would read as
            # the status of the run the user is about to start.
            self.export_error = ""
            self.export_result = ""
        self.export_confirm_pending = False

    def set_export_source(self, value: str | list[str]):
        raw = value[0] if isinstance(value, (list, tuple)) and value else value
        prefix = self.tr["export_source_manual_prefix"]
        self.export_source = "manual" if str(raw).startswith(prefix) else "filtros"
        self.export_confirm_pending = False

    def toggle_exp_report_figures(self, checked: bool):
        self.exp_report_figures = checked

    def toggle_exp_report_tables(self, checked: bool):
        self.exp_report_tables = checked

    def toggle_exp_points(self, checked: bool):
        self.exp_points = checked

    def toggle_exp_pixel(self, checked: bool):
        self.exp_pixel = checked

    def toggle_exp_buffers(self, checked: bool):
        self.exp_buffers = checked
        self.export_confirm_pending = False

    def toggle_exp_connectivity(self, checked: bool):
        self.exp_connectivity = checked
        self.export_confirm_pending = False

    def toggle_exp_full_area(self, checked: bool):
        self.exp_full_area = checked
        self.export_confirm_pending = False

    def set_exp_radius(self, value: str | list[str]):
        raw = value[0] if isinstance(value, (list, tuple)) and value else value
        label = str(raw)
        self.exp_radius = "" if label.startswith("Todos") else \
            label.replace(" km", "").strip()
        self.export_confirm_pending = False

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
        """The export request, assembled from the panel and the map.

        A pasted coordinate list wins outright when active: it is not another
        value of ``export_source`` (filters vs. manual) but a third, mutually
        exclusive point source — the same priority services.exports.SelectionSpec
        itself gives user_points over conglomerados over filters.
        """
        if self.user_points_active:
            return exports.SelectionSpec(
                user_points=plain(self.user_points),
                radii=self._radii(),
                buffer_shape=self.buffer_shape,
                include_points=self.exp_points, include_pixel=self.exp_pixel,
                include_buffers=self.exp_buffers,
                include_connectivity=self.exp_connectivity,
            )
        manual = self.export_source == "manual"
        return exports.SelectionSpec(
            region=self.ifn_region, uf=self.ifn_uf,
            municipality=self.ifn_municipality, biome=self.ifn_biome,
            conglomerados=plain(self.multi_conglomerados) if manual else None,
            radii=self._radii(),
            buffer_shape=self.buffer_shape,
            include_points=self.exp_points, include_pixel=self.exp_pixel,
            include_buffers=self.exp_buffers,
            include_connectivity=self.exp_connectivity,
            include_full_area=self.exp_full_area if manual else False,
        )

    @rx.var
    def export_source_options(self) -> list[str]:
        return [self.tr["export_source_map_filters"],
                f"{self.tr['export_source_manual_prefix']} ({self.multi_count})"]

    @rx.var
    def export_source_value(self) -> str:
        return (f"{self.tr['export_source_manual_prefix']} ({self.multi_count})"
                if self.export_source == "manual"
                else self.tr["export_source_map_filters"])

    @rx.var
    def export_manual_available(self) -> bool:
        # Hidden while a pasted list governs the export — the filter/manual
        # toggle has nothing to switch between in that case.
        return self.multi_count > 0 and not self.user_points_active

    @rx.var
    def export_selection_count(self) -> int:
        if self.user_points_active:
            return self.user_points_count
        if self.export_source == "manual":
            return self.multi_count
        return ifn.count(self.ifn_region, self.ifn_uf, self.ifn_municipality,
                         self.ifn_biome)

    @rx.var
    def export_selection_label(self) -> str:
        if self.user_points_active:
            return self.tr["export_selection_user_points"].format(
                n=self.user_points_count)
        if self.export_source == "manual":
            return self.tr["export_selection_manual"].format(n=self.multi_count)
        parts = [p for p in (self.ifn_region, self.ifn_biome, self.ifn_uf,
                             self.ifn_municipality) if p]
        return " · ".join(parts) if parts else self.tr["export_selection_whole_country"]

    @rx.var
    def export_count_label(self) -> str:
        n = self.export_selection_count
        text = f"{n:,}"
        if self.language == "pt":
            text = text.replace(",", ".")
        noun = self.tr["export_count_one" if n == 1 else "export_count_many"]
        return f"{text} {noun}"

    @rx.var
    def export_radius_options(self) -> list[str]:
        return [self.tr["export_radius_all"]] + [
            f"{r:g} km" for r in sorted(BUFFER_RADII_KM)]

    @rx.var
    def export_radius_value(self) -> str:
        return f"{float(self.exp_radius):g} km" if self.exp_radius \
            else self.tr["export_radius_all"]

    @rx.var
    def export_buffer_note(self) -> str:
        """What the buffer (+ connectivity, if checked) export will cost.
        Advisory — nothing is refused."""
        n = self.export_selection_count
        if n == 0:
            return self.tr["export_no_selection"]
        return exports.buffer_estimate_message(n, self._radii(), self.exp_connectivity)

    @rx.var
    def export_buffer_heavy(self) -> bool:
        """Big enough that the *download* is the risk, not the computation."""
        n = self.export_selection_count
        return bool(n) and exports.buffer_estimate(
            n, self._radii(), self.exp_connectivity)["heavy"]

    @rx.var
    def export_buffer_over_limit(self) -> bool:
        """The one refusal: past the largest-biome ceiling."""
        n = self.export_selection_count
        return bool(n) and exports.buffer_estimate(
            n, self._radii(), self.exp_connectivity)["over_limit"]

    @rx.var
    def export_progress_label(self) -> str:
        if not self.export_busy:
            return ""
        if self.export_total:
            return f"{self.export_stage} — {self.export_done}/{self.export_total}"
        return self.export_stage

    @rx.var
    def export_nothing_selected(self) -> bool:
        return not (self.exp_points or self.exp_pixel or self.exp_buffers
                    or self.exp_connectivity or self.exp_full_area)

    @rx.var
    def export_needs_confirmation(self) -> bool:
        """Whether the friction step applies: only the expensive fan-outs
        (buffers → land-cover + vegetation age + change mask, connectivity,
        and the full-area computation) cost real Earth Engine compute per
        click, so points-only/pixel-only exports stay a single click."""
        return ((self.exp_buffers or self.exp_connectivity or self.exp_full_area)
                and self.export_selection_count > 0)

    @rx.var
    def export_confirm_message(self) -> str:
        return exports.buffer_estimate_message(
            self.export_selection_count, self._radii(), self.exp_connectivity)

    # ---------------------------------------------------------------------- #
    # Study point
    # ---------------------------------------------------------------------- #

    @rx.event(background=True)
    async def download_study_point(self):
        """One spreadsheet for the location on screen. No Earth Engine calls."""
        async with self:
            if not self.has_result:
                self.export_error = self.tr["export_choose_point_first"]
                return
            self.export_busy = True
            self.export_stage = self.tr["export_stage_building_point"]
            self.export_error = ""
            self.export_result = ""

        # The vegetation-age/change fetch (state/_analysis.py run_analysis)
        # trails the land-cover history by a couple of seconds, so has_result
        # can already be true while it is still in flight — a click on "Baixar
        # dados" right after the chart appears used to ship idade_*/mudanca_*
        # tabs with only headers and a note buried in the metadata sheet. Wait
        # for it instead, bounded so a genuinely stuck fetch cannot hang the
        # download forever; past the bound the export still proceeds with
        # whatever landed, same as before.
        waited = 0.0
        while waited < 20.0:
            async with self:
                running = (self.age_running or self.landscape_metrics_running
                          or self.connectivity_running or self.biomass_running)
            if not running:
                break
            async with self:
                self.export_stage = self.tr["export_stage_waiting_age"]
            await asyncio.sleep(0.4)
            waited += 0.4

        async with self:
            self.export_stage = self.tr["export_stage_building_point"]
            history, prov = plain(self._history), plain(self._provenance)
            pixel, pixel_prov = plain(self._pixel), plain(self._pixel_provenance)
            age_point = plain(self._age_point)
            age_point_prov = plain(self._age_point_provenance)
            age_buffers = plain(self._age_buffers)
            age_buffers_prov = plain(self._age_buffers_provenance)
            change = plain(self._change_stats)
            change_prov = plain(self._change_provenance)
            landscape_metrics = plain(self._landscape_metrics)
            landscape_metrics_prov = plain(self._landscape_metrics_provenance)
            connectivity = plain(self._connectivity)
            connectivity_prov = plain(self._connectivity_provenance)
            biomass = plain(self._biomass)
            biomass_prov = plain(self._biomass_provenance)
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
                pixel_prov, identity, age_point, age_point_prov, age_buffers,
                age_buffers_prov, change, change_prov, landscape_metrics,
                landscape_metrics_prov, connectivity, connectivity_prov,
                biomass, biomass_prov, self.buffer_shape)
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

    @rx.var
    def export_report_any(self) -> bool:
        return self.exp_report_figures or self.exp_report_tables

    @rx.event(background=True)
    async def download_study_point_report(self):
        """The "paper-friendly" HTML report (services.report) — a separate
        download from the ODS above, not a second file the same click
        produces: two near-simultaneous rx.download calls risk a browser's
        own multiple-download prompt, and the two files answer different
        questions anyway (read this vs. reprocess that)."""
        async with self:
            if not self.has_result:
                self.export_error = self.tr["export_choose_point_first"]
                return
            if not self.export_report_any:
                return
            self.export_busy = True
            self.export_stage = self.tr["export_stage_building_point"]
            self.export_error = ""
            self.export_result = ""

        # Same wait as download_study_point above — the report reads whatever
        # has landed in state, and a click right after the chart appears must
        # not ship a report with blank figures/tables for fetches still in
        # flight (doc/11 §5, same reasoning, same bound).
        waited = 0.0
        while waited < 20.0:
            async with self:
                running = (self.age_running or self.landscape_metrics_running
                          or self.biomass_running)
            if not running:
                break
            async with self:
                self.export_stage = self.tr["export_stage_waiting_age"]
            await asyncio.sleep(0.4)
            waited += 0.4

        async with self:
            self.export_stage = self.tr["export_stage_building_point"]
            history, prov = plain(self._history), plain(self._provenance)
            age_buffers = plain(self._age_buffers)
            age_buffers_prov = plain(self._age_buffers_provenance)
            change = plain(self._change_stats)
            landscape_metrics = plain(self._landscape_metrics)
            landscape_metrics_prov = plain(self._landscape_metrics_provenance)
            connectivity = plain(self._connectivity)
            connectivity_prov = plain(self._connectivity_provenance)
            biomass = plain(self._biomass)
            biomass_prov = plain(self._biomass_provenance)
            lat, lon, shape = self.study_lat, self.study_lon, self.buffer_shape
            include_figures, include_tables = (self.exp_report_figures,
                                               self.exp_report_tables)
            lang = self.language
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
                None, _build_study_point_report, lat, lon, history, prov,
                identity, age_buffers, age_buffers_prov, change,
                landscape_metrics, landscape_metrics_prov, connectivity,
                connectivity_prov, biomass, biomass_prov, shape,
                include_figures, include_tables, lang)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Study-point report failed")
            async with self:
                self.export_busy = False
                self.export_error = f"Falha ao gerar o relatório: {exc}"
            return

        async with self:
            self.export_busy = False
            self.export_stage = ""
            self.export_result = f"{name} ({len(data) // 1024} KiB)"
        return rx.download(data=data, filename=name, mime_type="text/html")

    # ---------------------------------------------------------------------- #
    # Conglomerado selection
    # ---------------------------------------------------------------------- #

    def request_selection_download(self):
        """The button's actual on_click — the friction step in front of
        download_selection.

        Only the expensive path (buffers) asks twice; a points-only or
        pixel-only export — already unthrottled, since it costs a couple of
        seconds no matter the size — stays one click. This is a UI-level
        deterrent for a human clicking by mistake or on reflex, not the
        enforcement: a script calling the Reflex event directly skips this
        entirely, which is exactly why download_selection *also* checks
        services.abuse_control regardless of how it was reached.
        """
        if not self.export_needs_confirmation or self.export_confirm_pending:
            self.export_confirm_pending = False
            return type(self).download_selection()
        self.export_confirm_pending = True
        return None

    def cancel_selection_download(self):
        self.export_confirm_pending = False

    @rx.event(background=True)
    async def download_selection(self):
        """One spreadsheet covering every conglomerado the filters select."""
        async with self:
            spec = self._spec()
            if self.export_nothing_selected:
                self.export_error = self.tr["export_no_datasets"]
                return
            self.export_confirm_pending = False
            self.export_busy = True
            self.export_error = ""
            self.export_result = ""
            self.export_done = 0
            self.export_total = 0
            self.export_stage = self.tr["export_stage_gathering"]
            client_ip = self.router.session.client_ip
            client_token = self.router.session.client_token
            session_id = self.router.session.session_id

        if ((spec.include_buffers or spec.include_connectivity)
                and len(spec.points()) > EXPORT_MAX_BUFFER_POINTS):
            async with self:
                self.export_busy = False
                self.export_error = exports.buffer_estimate_message(
                    len(spec.points()), spec.radii, spec.include_connectivity)
            return

        points = spec.points()
        if not points:
            async with self:
                self.export_busy = False
                self.export_error = self.tr["export_no_selection"]
            return

        loop = asyncio.get_running_loop()

        # The rate-limit gate: only the buffer fan-out costs real Earth Engine
        # compute per click (see services/abuse_control.py). Both checks hit
        # GCS, so they run off the event loop like every other blocking call
        # here, and both fail OPEN on a bucket error rather than blocking a
        # real user for an infrastructure hiccup.
        if spec.include_buffers or spec.include_connectivity:
            ok, reason = await loop.run_in_executor(
                None, abuse_control.check_session_cooldown, client_token)
            if ok:
                ok, reason = await loop.run_in_executor(
                    None, abuse_control.check_ip_rate_limit, client_ip)
            outcome = "allowed" if ok else "refused"
            await loop.run_in_executor(
                None, lambda: abuse_control.log_event(
                    ip=client_ip, client_token=client_token,
                    session_id=session_id, action="bulk_export",
                    outcome=outcome,
                    detail={"n_points": len(points), "radii": list(spec.radii),
                            "reason": reason} if not ok else
                           {"n_points": len(points), "radii": list(spec.radii)}))
            if not ok:
                async with self:
                    self.export_busy = False
                    self.export_error = reason
                return

        pixel = buffers = age = change = landscape_metrics = None
        connectivity = biomass = None

        try:
            if spec.include_pixel:
                async with self:
                    self.export_stage = self.tr["export_stage_reading_pixel"]
                pixel = await loop.run_in_executor(
                    None, exports.selection_pixel_frame, spec)

            async def fan_out(fn, stage: str):
                """One per-point fan-out with a live done/total counter.

                Buffers, vegetation age and the change mask are three separate
                Earth Engine products (mapbiomas_history, vegetation_age,
                change_mask) fanned out the same way, sequentially — this is the
                one place that shape lives rather than three copies that could
                drift apart. The callback itself runs on an Earth Engine worker
                thread, so it cannot touch state directly; it drops the counter
                somewhere this coroutine can read and publish.
                """
                async with self:
                    self.export_stage = stage
                    self.export_done = 0
                    self.export_total = len(points)
                counter = {"done": 0}

                def progress(done: int, total: int) -> None:
                    counter["done"] = done

                task = loop.run_in_executor(None, fn, spec, points, progress)
                while not task.done():
                    await asyncio.sleep(0.5)
                    async with self:
                        self.export_done = counter["done"]
                return await task

            if spec.include_buffers:
                buffers = await fan_out(exports.selection_buffer_frame,
                                        self.tr["export_stage_computing_landuse"])
                age = await fan_out(exports.selection_age_frame,
                                    self.tr["export_stage_computing_age"])
                change = await fan_out(exports.selection_change_frame,
                                       self.tr["export_stage_computing_change"])
                landscape_metrics = await fan_out(
                    exports.selection_landscape_metrics_frame,
                    self.tr["export_stage_computing_metrics"])
                biomass = await fan_out(exports.selection_biomass_frame,
                                        self.tr["export_stage_computing_biomass"])

            if spec.include_connectivity:
                connectivity = await fan_out(
                    exports.selection_connectivity_frame,
                    self.tr["export_stage_computing_connectivity"])

            full_area = None
            if spec.include_full_area and spec.is_manual:
                async with self:
                    self.export_stage = self.tr["export_stage_computing_full_area"]
                full_area = await loop.run_in_executor(
                    None, exports.selection_full_area_frame, spec, points)

            async with self:
                self.export_stage = self.tr["export_stage_building_sheet"]
            data, name = await loop.run_in_executor(
                None, exports.selection_workbook, spec, points, pixel, buffers,
                age, change, landscape_metrics, connectivity, biomass, full_area)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Selection export failed")
            async with self:
                self.export_busy = False
                self.export_stage = ""
                self.export_error = self.tr["export_sheet_failed"].format(exc=exc)
            return

        async with self:
            self.export_busy = False
            self.export_stage = ""
            self.export_done = self.export_total
            # Union across the passes: a point can fail land-cover history but
            # succeed at vegetation age, or vice versa, and each row is a
            # single conglomerado's worth of missing data either way.
            failed = sorted(set(
                (buffers[2] if buffers else [])
                + (age[2] if age else [])
                + (change[2] if change else [])
                + (landscape_metrics[2] if landscape_metrics else [])
                + (connectivity[2] if connectivity else [])
                + (biomass[2] if biomass else [])
            ))
            note = (self.tr["export_result_failed_note"].format(n=len(failed))
                    if failed else "")
            self.export_result = f"{name} ({len(data) // 1024} KiB){note}"
        return rx.download(data=data, filename=name, mime_type=MIMETYPE)


def _build_study_point(lat, lon, history, prov, pixel, pixel_prov, identity,
                       age_point=None, age_point_prov=None, age_buffers=None,
                       age_buffers_prov=None, change=None, change_prov=None,
                       landscape_metrics=None, landscape_metrics_prov=None,
                       connectivity=None, connectivity_prov=None,
                       biomass=None, biomass_prov=None, buffer_shape="circle"):
    """Rebuild the frames and write the workbook, off the event loop."""
    import pandas as pd

    from ..services.geo import point
    from ..services.provenance import Provenance

    def revive(d: dict | None) -> Provenance | None:
        # State stores provenance as a plain dict so it can be serialised; the
        # workbook wants the dataclass back. Round-tripping through the class is
        # what keeps the two from drifting into different shapes. Empty means the
        # age/change fetch had not finished when the download was requested —
        # study_point_workbook treats a missing provenance as "not available yet",
        # not as an error.
        return Provenance(**d) if d else None

    change = {float(k): v for k, v in (change or {}).items()}

    return exports.study_point_workbook(
        point(lat=lat, lon=lon),
        pd.DataFrame(history), revive(prov),
        pd.DataFrame(pixel), revive(pixel_prov),
        identity=identity,
        age_point=pd.DataFrame(age_point) if age_point else None,
        age_point_prov=revive(age_point_prov),
        age_buffers=pd.DataFrame(age_buffers) if age_buffers else None,
        age_buffers_prov=revive(age_buffers_prov),
        change=change,
        change_prov=revive(change_prov),
        landscape_metrics=pd.DataFrame(landscape_metrics) if landscape_metrics else None,
        landscape_metrics_prov=revive(landscape_metrics_prov),
        connectivity=pd.DataFrame(connectivity) if connectivity else None,
        connectivity_prov=revive(connectivity_prov),
        biomass=pd.DataFrame(biomass) if biomass else None,
        biomass_prov=revive(biomass_prov),
        buffer_shape=buffer_shape,
    )


def _build_study_point_report(lat, lon, history, prov, identity, age_buffers,
                              age_buffers_prov, change, landscape_metrics,
                              landscape_metrics_prov, connectivity,
                              connectivity_prov, biomass, biomass_prov,
                              buffer_shape, include_figures, include_tables, lang):
    """Rebuild the frames and write the report, off the event loop — same
    revive-from-dict shape as _build_study_point above, minus the pixel
    series the report does not carry (it is a single-pixel caveat table, not
    a figure or a headline number)."""
    import pandas as pd

    from ..services.geo import point
    from ..services.provenance import Provenance
    from ..services.report import study_point_report_html

    def revive(d: dict | None) -> Provenance | None:
        return Provenance(**d) if d else None

    change = {float(k): v for k, v in (change or {}).items()}

    return study_point_report_html(
        point(lat=lat, lon=lon),
        pd.DataFrame(history), revive(prov) or Provenance(
            name="landuse_history", dataset_id=""),
        identity=identity,
        age_buffers=pd.DataFrame(age_buffers) if age_buffers else None,
        age_buffers_prov=revive(age_buffers_prov),
        change=change,
        landscape_metrics=pd.DataFrame(landscape_metrics) if landscape_metrics else None,
        landscape_metrics_prov=revive(landscape_metrics_prov),
        connectivity=pd.DataFrame(connectivity) if connectivity else None,
        connectivity_prov=revive(connectivity_prov),
        biomass=pd.DataFrame(biomass) if biomass else None,
        biomass_prov=revive(biomass_prov),
        buffer_shape=buffer_shape,
        include_figures=include_figures, include_tables=include_tables,
        lang=lang,
    )
