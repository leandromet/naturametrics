"""Climate, fire weather, Köppen and relief at the clicked point: the world page's "Climate" tab.

One independent answer with its own running line and error channel, like the other analyses, so a
failure here never blanks the land-cover or forest panels.
"""

from __future__ import annotations

import asyncio
import logging

import reflex as rx

from ..services import climate_rows
from ..services.geo import point

logger = logging.getLogger(__name__)


class WorldClimateMixin(rx.State, mixin=True):
    climate_rows: list[dict[str, str]] = []
    climate_running: bool = False
    climate_error: str = ""

    @rx.event(background=True)
    async def run_climate_terrain(self, lat: float, lon: float):
        async with self:
            token = self._run_token
            self.climate_running = True
            self.climate_error = ""
            lang = self.language
        loop = asyncio.get_running_loop()
        p = point(lat=lat, lon=lon)
        try:
            rows = await loop.run_in_executor(None, climate_rows.build_rows, p.lat, p.lon, lang)
        except Exception as exc:  # noqa: BLE001 — shown in the tab, not raised
            logger.exception("world climate analysis failed")
            async with self:
                if token == self._run_token:
                    self.climate_running = False
                    self.climate_error = self.tr["err_extra_failed"].format(exc=exc)
            return
        async with self:
            if token != self._run_token:
                return
            self.climate_rows = rows
            self.climate_running = False
