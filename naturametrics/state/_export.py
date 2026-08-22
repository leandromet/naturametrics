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

    def toggle_exp_points(self, checked: bool):
        self.exp_points = checked

    def toggle_exp_pixel(self, checked: bool):
        self.exp_pixel = checked

    def toggle_exp_buffers(self, checked: bool):
        self.exp_buffers = checked
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
        """What the buffer export will cost. Advisory — nothing is refused."""
        n = self.export_selection_count
        if n == 0:
            return self.tr["export_no_selection"]
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

    @rx.var
    def export_needs_confirmation(self) -> bool:
        """Whether the friction step applies: only the expensive fan-out
        (buffers → land-cover + vegetation age + change mask) costs real Earth
        Engine compute per click, so points-only/pixel-only exports stay a
        single click."""
        return self.exp_buffers and self.export_selection_count > 0

    @rx.var
    def export_confirm_message(self) -> str:
        return exports.buffer_estimate_message(self.export_selection_count,
                                               self._radii())

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
                running = self.age_running
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
                age_buffers_prov, change, change_prov, self.buffer_shape)
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
                self.export_error = self.tr["export_no_selection"]
            return

        loop = asyncio.get_running_loop()

        # The rate-limit gate: only the buffer fan-out costs real Earth Engine
        # compute per click (see services/abuse_control.py). Both checks hit
        # GCS, so they run off the event loop like every other blocking call
        # here, and both fail OPEN on a bucket error rather than blocking a
        # real user for an infrastructure hiccup.
        if spec.include_buffers:
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

        pixel = buffers = age = change = None

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

            async with self:
                self.export_stage = self.tr["export_stage_building_sheet"]
            data, name = await loop.run_in_executor(
                None, exports.selection_workbook, spec, points, pixel, buffers,
                age, change)
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
            # Union across the three passes: a point can fail land-cover history
            # but succeed at vegetation age, or vice versa, and each row is a
            # single conglomerado's worth of missing data either way.
            failed = sorted(set(
                (buffers[2] if buffers else [])
                + (age[2] if age else [])
                + (change[2] if change else [])
            ))
            note = (self.tr["export_result_failed_note"].format(n=len(failed))
                    if failed else "")
            self.export_result = f"{name} ({len(data) // 1024} KiB){note}"
        return rx.download(data=data, filename=name, mime_type=MIMETYPE)


def _build_study_point(lat, lon, history, prov, pixel, pixel_prov, identity,
                       age_point=None, age_point_prov=None, age_buffers=None,
                       age_buffers_prov=None, change=None, change_prov=None,
                       buffer_shape="circle"):
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
        buffer_shape=buffer_shape,
    )
