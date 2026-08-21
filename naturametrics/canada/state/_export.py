"""Download state for the Canada page.

Only the study-point export. The Brazil page also exports a *selection* of IFN
conglomerados, which is the expensive fan-out that needs rate limiting and a
confirmation step; Canada has no equivalent point grid, so there is nothing here
that costs more than the analysis already on screen — no Earth Engine call at
all, in fact, since every number was computed to draw the charts.
"""

from __future__ import annotations

import asyncio
import logging

import reflex as rx

from ...services.ods import MIMETYPE
from ...state._proxy import plain
from ..services.exports import study_point_workbook

logger = logging.getLogger(__name__)


class CanadaExportMixin(rx.State, mixin=True):
    """The download dialog."""

    export_open: bool = False
    export_busy: bool = False
    export_error: str = ""
    export_result: str = ""

    def set_export_open(self, value: bool):
        self.export_open = value
        if value:
            # Stale text from a previous run would read as this run's status.
            self.export_error = ""
            self.export_result = ""

    @rx.event(background=True)
    async def download_study_point(self):
        """One spreadsheet for the location on screen. No Earth Engine calls."""
        async with self:
            if not self.has_result:
                self.export_error = self.tr["export_choose_point_first"]
                return
            self.export_busy = True
            self.export_error = ""
            self.export_result = ""

        # The forest half trails the crop-inventory half by a second or two, so
        # has_result can be true while age/change are still in flight. Wait,
        # bounded, rather than shipping tabs with only headers.
        waited = 0.0
        while waited < 20.0:
            async with self:
                running = self.age_running
            if not running:
                break
            await asyncio.sleep(0.4)
            waited += 0.4

        async with self:
            payload = dict(
                point_label=self.point_label,
                lat=self.study_lat,
                lon=self.study_lon,
                history=plain(self._history),
                history_prov=plain(self._provenance),
                pixel=plain(self._pixel),
                pixel_prov=plain(self._pixel_provenance),
                age=plain(self._age_buffers),
                age_prov=plain(self._age_provenance),
                point_age=plain(self._age_point),
                change=plain(self._change_stats),
                change_prov=plain(self._change_provenance),
                loss_series=plain(self._loss_series),
            )

        loop = asyncio.get_running_loop()
        try:
            data, name = await loop.run_in_executor(
                None, lambda: study_point_workbook(**payload))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Canada study-point export failed")
            async with self:
                self.export_busy = False
                self.export_error = self.tr["export_sheet_failed"].format(exc=exc)
            return

        async with self:
            self.export_busy = False
            self.export_result = f"{name} ({len(data) // 1024} KiB)"
        return rx.download(data=data, filename=name, mime_type=MIMETYPE)
