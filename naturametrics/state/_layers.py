"""Map layer state: basemap, MapBiomas year, opacity, and the layer list.

The layer list is plain state rather than a computed var on purpose. Building it
can require minting Earth Engine tile URLs, and a computed var that makes network
calls would run on every state read — including reads that have nothing to do
with the map.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import reflex as rx

from ..config import datasets as ds
from ..config import mapbiomas as mb
from ..config import settings as st
from ..services import change_mask as cm
from ..services import layers as layer_service

logger = logging.getLogger(__name__)


class LayersMixin(rx.State, mixin=True):
    """Which layers are on the map, and what the map is showing."""

    # --- view -------------------------------------------------------------
    map_center: list[float] = [st.MAP_CENTER[0], st.MAP_CENTER[1]]
    map_zoom: int = st.MAP_ZOOM
    map_bounds: list[list[float]] = [list(st.BRAZIL_VIEW_BOUNDS[0]),
                                     list(st.BRAZIL_VIEW_BOUNDS[1])]

    # --- layer selection --------------------------------------------------
    basemap: str = ds.DEFAULT_BASEMAP
    show_mapbiomas: bool = False
    mapbiomas_year: int = mb.MAPBIOMAS_YEAR_END
    mapbiomas_opacity: float = 0.75

    #: Swipe comparison: a second MapBiomas year, split by a draggable divider.
    #: The two sides carry independent opacity — the point of the comparison is
    #: often to fade one side against the basemap while keeping the other solid,
    #: which a single shared control cannot express.
    compare_enabled: bool = False
    compare_year: int = cm.FOREST_CODE_BASELINE_YEAR
    compare_opacity: float = 0.75

    #: Change mask: natural vegetation lost / regrown since the baseline year.
    show_change_mask: bool = False
    change_from_year: int = cm.FOREST_CODE_BASELINE_YEAR
    change_include_stable: bool = False
    change_mask_url: str = ""

    # --- what the map component receives ----------------------------------
    #: Seeded with the default basemap at class-definition time, so the map has
    #: something to draw on the very first render. Waiting for the `initialise`
    #: background event would leave a grey rectangle until the backend
    #: WebSocket connects — and if the backend is slow, restarting, or has
    #: crashed, that grey rectangle is all the user ever sees. The basemap is
    #: a plain XYZ URL from config: no Earth Engine, no credentials, no I/O.
    map_layers: list[dict[str, Any]] = [
        spec for spec in [layer_service.basemap_spec(ds.DEFAULT_BASEMAP, z_index=0)]
        if spec
    ]

    # --- status -----------------------------------------------------------
    ee_ready: bool = False
    ee_error: str = ""
    layer_busy: bool = False
    prefetch_done: int = 0
    prefetch_total: int = 0

    #: Backend-only cache of year → tile URL. The leading underscore keeps it
    #: out of the browser: 40 signed URLs are not something to ship to a client.
    _mb_urls: dict[int, str] = {}

    # ---------------------------------------------------------------------- #
    # Layer assembly
    # ---------------------------------------------------------------------- #

    def _build_layers(self) -> list[dict[str, Any]]:
        """Assemble the ordered layer list from current selections."""
        specs: list[dict[str, Any]] = []

        base = layer_service.basemap_spec(self.basemap, z_index=0)
        if base:
            specs.append(base)

        if self.show_mapbiomas:
            url = self._mb_urls.get(self.mapbiomas_year)
            if url:
                specs.append({
                    "id": f"mapbiomas:{mb.MAPBIOMAS_DEFAULT_COLLECTION}:{self.mapbiomas_year}",
                    "url": url,
                    "opacity": self.mapbiomas_opacity,
                    "attribution": "MapBiomas Collection 10.1",
                    "z_index": 10,
                    "max_native_zoom": 15,
                    # In compare mode the active year takes the RIGHT half; the
                    # baseline year sits underneath on the left.
                    "clip": "right" if self.compare_enabled else None,
                })

            if self.compare_enabled:
                url_b = self._mb_urls.get(self.compare_year)
                if url_b:
                    specs.append({
                        "id": f"mapbiomas:{mb.MAPBIOMAS_DEFAULT_COLLECTION}:{self.compare_year}:cmp",
                        "url": url_b,
                        "opacity": self.compare_opacity,
                        "attribution": "MapBiomas Collection 10.1",
                        "z_index": 11,
                        "max_native_zoom": 15,
                        "clip": "left",
                    })

        if self.show_change_mask and self.change_mask_url:
            specs.append({
                "id": (f"change:{self.change_from_year}-{mb.MAPBIOMAS_YEAR_END}"
                       f":{'stable' if self.change_include_stable else 'nostable'}"),
                "url": self.change_mask_url,
                "opacity": 0.85,
                "attribution": (f"MapBiomas mudança {self.change_from_year}"
                                f"\u2192{mb.MAPBIOMAS_YEAR_END}"),
                "z_index": 20,
                "max_native_zoom": 15,
            })
        return specs

    def _refresh_layers(self) -> None:
        self.map_layers = self._build_layers()

    # ---------------------------------------------------------------------- #
    # Event handlers
    # ---------------------------------------------------------------------- #

    def set_basemap(self, key: str):
        """Swap the basemap. The map instance is untouched, so the view holds."""
        self.basemap = key
        self._refresh_layers()

    def set_mapbiomas_opacity(self, value: list[int | float]):
        """Slider gives a list; Reflex sliders are range-capable."""
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.mapbiomas_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    def set_compare_opacity(self, value: list[int | float]):
        """Opacity of the left (baseline) year in swipe comparison."""
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.compare_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    @rx.event(background=True)
    async def toggle_compare(self, checked: bool):
        """Show two MapBiomas years side by side, split by a draggable divider."""
        async with self:
            self.compare_enabled = checked
            if not checked:
                self._refresh_layers()
                return
            if not self.show_mapbiomas:
                self.show_mapbiomas = True
            needed = self.compare_year not in self._mb_urls
            if not needed:
                self._refresh_layers()
                return
            self.layer_busy = True
        await self._ensure_year(self.compare_year)

    @rx.event(background=True)
    async def set_compare_year(self, value: list[int | float] | int | str):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        try:
            year = int(raw)
        except (TypeError, ValueError):
            return
        async with self:
            self.compare_year = year
            if not self.compare_enabled or year in self._mb_urls:
                self._refresh_layers()
                return
            self.layer_busy = True
        await self._ensure_year(year)

    @rx.event(background=True)
    async def toggle_change_mask(self, checked: bool):
        """Natural vegetation lost or regrown since the Forest Code baseline."""
        async with self:
            self.show_change_mask = checked
            if not checked:
                self._refresh_layers()
                return
            if self.change_mask_url:
                self._refresh_layers()
                return
            self.layer_busy = True

        loop = asyncio.get_running_loop()
        try:
            spec = await loop.run_in_executor(
                None, cm.change_mask_spec, self.change_from_year,
                mb.MAPBIOMAS_YEAR_END, 0.85, self.change_include_stable,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Change mask failed: %s", exc)
            spec = None

        async with self:
            self.change_mask_url = spec["url"] if spec else ""
            self.layer_busy = False
            self._refresh_layers()

    @rx.event(background=True)
    async def set_change_from_year(self, value: list[int | float] | int | str):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        try:
            year = int(raw)
        except (TypeError, ValueError):
            return
        async with self:
            self.change_from_year = year
            self.change_mask_url = ""
            if not self.show_change_mask:
                return
            self.layer_busy = True

        loop = asyncio.get_running_loop()
        try:
            spec = await loop.run_in_executor(
                None, cm.change_mask_spec, year, mb.MAPBIOMAS_YEAR_END, 0.85,
                self.change_include_stable,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Change mask failed: %s", exc)
            spec = None

        async with self:
            self.change_mask_url = spec["url"] if spec else ""
            self.layer_busy = False
            self._refresh_layers()

    @rx.event(background=True)
    async def initialise(self):
        """Bring Earth Engine up and warm the MapBiomas tile cache.

        Runs in the background so the map paints immediately rather than waiting
        on Earth Engine — the basemap needs no credentials at all.
        """
        async with self:
            self._refresh_layers()  # basemap first: instant, no EE required

        loop = asyncio.get_running_loop()
        try:
            from ..services.ee_client import initialize_earth_engine
            await loop.run_in_executor(None, initialize_earth_engine)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Earth Engine initialisation failed")
            async with self:
                self.ee_error = str(exc)
            return

        async with self:
            self.ee_ready = True
            self.prefetch_total = len(mb.MAPBIOMAS_YEARS)

        # Speculative prefetch (doc/06 §5b) in two stages, so a cold instance is
        # usable before the full sweep lands: the years around the current one
        # first, then everything else. Measured at ~1.4 s for all 40 warm, but on
        # a fresh Cloud Run container the first user pays that, and the window
        # makes the first slider movements instant regardless.
        try:
            window = await loop.run_in_executor(
                None, layer_service.prefetch_window, self.mapbiomas_year, 5
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("MapBiomas window prefetch failed: %s", exc)
            window = {}

        async with self:
            self._mb_urls.update({y: u for y, u in window.items() if u})
            self.prefetch_done = len(self._mb_urls)
            self._refresh_layers()

        try:
            rest = await loop.run_in_executor(
                None, layer_service.prefetch_mapbiomas_years,
                mb.MAPBIOMAS_YEARS, mb.MAPBIOMAS_DEFAULT_COLLECTION, set(self._mb_urls),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("MapBiomas prefetch failed: %s", exc)
            return

        async with self:
            self._mb_urls.update({y: u for y, u in rest.items() if u})
            self.prefetch_done = len(self._mb_urls)
            self._refresh_layers()

    @rx.event(background=True)
    async def toggle_mapbiomas(self, checked: bool):
        """Show or hide the MapBiomas layer, minting on demand if prefetch has not landed."""
        async with self:
            self.show_mapbiomas = checked
            if not checked:
                self._refresh_layers()
                return
            have_url = self.mapbiomas_year in self._mb_urls
            if have_url:
                self._refresh_layers()
                return
            self.layer_busy = True

        await self._ensure_year(self.mapbiomas_year)

    @rx.event(background=True)
    async def set_mapbiomas_year(self, value: list[int | float] | int | str):
        """Move to a different MapBiomas year.

        With the cache warm this is a dictionary lookup and the layer swaps
        without the map moving — which is the whole point of decision D1.
        """
        raw = value[0] if isinstance(value, (list, tuple)) else value
        try:
            year = int(raw)
        except (TypeError, ValueError):
            return

        async with self:
            self.mapbiomas_year = year
            if not self.show_mapbiomas or year in self._mb_urls:
                self._refresh_layers()
                return
            self.layer_busy = True

        await self._ensure_year(year)

    async def _ensure_year(self, year: int) -> None:
        """Mint one year's tile URL off the event loop, then refresh."""
        loop = asyncio.get_running_loop()
        try:
            spec = await loop.run_in_executor(None, layer_service.mapbiomas_spec, year)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not build MapBiomas %s: %s", year, exc)
            spec = None

        async with self:
            if spec:
                self._mb_urls[year] = spec["url"]
            self.layer_busy = False
            self._refresh_layers()

    # ---------------------------------------------------------------------- #
    # Derived display values
    # ---------------------------------------------------------------------- #

    @rx.var
    def opacity_pct(self) -> int:
        return int(round(self.mapbiomas_opacity * 100))

    @rx.var
    def compare_opacity_pct(self) -> int:
        return int(round(self.compare_opacity * 100))

    @rx.var
    def ee_status_label(self) -> str:
        if self.ee_error:
            return "Earth Engine indisponível"
        if not self.ee_ready:
            return "Conectando ao Earth Engine…"
        if self.prefetch_total and self.prefetch_done < self.prefetch_total:
            return f"Pré-carregando anos… {self.prefetch_done}/{self.prefetch_total}"
        return f"Earth Engine pronto — {self.prefetch_done} anos em cache"
