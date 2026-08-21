"""Map layer state for the Canada page.

Same shape as the Brazil page's layer state and for the same reason: the layer
list is plain state rather than a computed var, because building it can require
minting Earth Engine tile URLs and a computed var would re-run that on every
read.

Four toggleable Earth Engine layers, each independent: the ACI classification for
one year, NTEMS stand age, Hansen tree cover, and the Hansen loss/gain mask —
plus the annual Landsat composite, which behaves as an *overlay on* the chosen
base map rather than a base map of its own (same as Brazil's SPOT mosaics).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import reflex as rx

from ...config.settings import (
    BUFFER_PREVIEW_OPACITY, BUFFER_PREVIEW_RADIUS_KM, BUFFER_PREVIEW_SHAPE,
)
from ...services.ee_client import get_ee
from ..config import aafc
from ..config import datasets as ds
from ..config import forest as fc_cfg
from ..config import settings as ca_st
from ..services import layers as layer_service

logger = logging.getLogger(__name__)


class CanadaLayersMixin(rx.State, mixin=True):
    """Which layers are on the map, and what the map is showing."""

    # --- view -------------------------------------------------------------
    map_center: list[float] = [ca_st.MAP_CENTER[0], ca_st.MAP_CENTER[1]]
    map_zoom: int = ca_st.MAP_ZOOM
    map_bounds: list[list[float]] = [list(ca_st.CANADA_VIEW_BOUNDS[0]),
                                     list(ca_st.CANADA_VIEW_BOUNDS[1])]
    #: ``[[s, w], [n, e]]`` re-applied imperatively whenever it changes; empty
    #: means "leave the viewport alone". Initial framing is ``map_bounds`` above.
    #: The Brazil page drives this from its IFN filters; Canada has no
    #: filter-driven re-framing, so it stays empty and the user keeps their view.
    fit_bounds: list[list[float]] = []

    map_layers: list[dict[str, Any]] = []
    buffer_overlays: dict[str, Any] = {}
    map_vectors: list[dict[str, Any]] = []

    # --- base map ---------------------------------------------------------
    basemap: str = ds.DEFAULT_BASEMAP
    basemap_error: str = ""

    # --- ACI --------------------------------------------------------------
    show_aci: bool = False
    aci_year: int = aafc.ACI_YEAR_END
    aci_opacity: float = 0.75

    # --- buffer preview ("magnifying glass") ------------------------------
    #: Shows the crop inventory *only inside* the analysis radius around the
    #: clicked point, and nowhere else. Costs no Earth Engine call: the tile URL
    #: is minted once at startup and the restriction to a circle is a CSS clip
    #: applied in the browser (see leaflet_map.js).
    #:
    #: Always the **most recent** ACI year rather than whatever the year slider
    #: happens to be on — the magnifier answers "what is here now", and pairing
    #: it with a slider the user moved for a different purpose would make it
    #: quietly disagree with itself.
    show_buffer_preview: bool = True
    preview_points: list[list[float]] = []

    # --- NTEMS forest age -------------------------------------------------
    show_forest_age: bool = False
    forest_age_opacity: float = 0.75

    # --- Hansen -----------------------------------------------------------
    show_treecover: bool = False
    treecover_opacity: float = 0.6
    show_change: bool = False
    change_from_year: int = fc_cfg.HANSEN_LOSS_YEAR_START
    treecover_threshold: int = fc_cfg.HANSEN_TREECOVER_THRESHOLD

    # --- Landsat ----------------------------------------------------------
    show_landsat: bool = False
    landsat_rendering: str = "landsat_true"
    landsat_year: int = 2024

    # --- engine status ----------------------------------------------------
    ee_ready: bool = False
    ee_error: str = ""
    layer_busy: bool = False

    #: Minted tile URLs, keyed by layer id. Kept so a toggle that has already
    #: been on once repaints with no round-trip at all.
    _url_cache: dict[str, str] = {}

    # ---------------------------------------------------------------------- #
    # Layer assembly
    # ---------------------------------------------------------------------- #

    def _build_layers(self) -> list[dict[str, Any]]:
        """Assemble the ordered layer list from the current selections."""
        specs: list[dict[str, Any]] = []

        base = layer_service.basemap_spec(self.basemap, z_index=0)
        if base:
            specs.append(base)

        for key, spec in self._cached_specs():
            if spec:
                specs.append(spec)
        return specs

    def _cached_specs(self):
        """Yield (id, spec) for every enabled Earth Engine layer.

        Reads only ``_url_cache``; nothing here mints. Minting happens in the
        background events below, which then call ``_refresh_layers``.
        """
        if self.show_landsat:
            lid = f"ca:landsat:{self.landsat_rendering}:{self.landsat_year}"
            url = self._url_cache.get(lid)
            if url:
                yield lid, {
                    "id": lid, "url": url, "opacity": 1.0,
                    "attribution": f"{ds.LANDSAT_ATTRIBUTION} — {self.landsat_year}",
                    "z_index": 1, "max_native_zoom": 14,
                }

        if self.show_aci:
            lid = f"ca:aci:{self.aci_year}"
            url = self._url_cache.get(lid)
            if url:
                yield lid, {
                    "id": lid, "url": url, "opacity": self.aci_opacity,
                    "attribution": f"{layer_service.ACI_ATTRIBUTION} {self.aci_year}",
                    "z_index": 10, "max_native_zoom": 15,
                }

        # Suppressed while the full ACI layer is on — the coverage is already
        # painted across the whole map, so a magnifier over it shows nothing new.
        if self.show_buffer_preview and self.preview_points and not self.show_aci:
            lid = f"ca:aci:{aafc.ACI_YEAR_END}"
            url = self._url_cache.get(lid)
            if url:
                yield f"ca:preview:{aafc.ACI_YEAR_END}", {
                    "id": f"ca:preview:{aafc.ACI_YEAR_END}",
                    "url": url,
                    "opacity": BUFFER_PREVIEW_OPACITY,
                    "attribution": (f"{layer_service.ACI_ATTRIBUTION} "
                                    f"{aafc.ACI_YEAR_END}"),
                    "z_index": 13, "max_native_zoom": 15,
                    "clip_circles": [{"lat": lat, "lon": lon}
                                     for lat, lon in self.preview_points],
                    "clip_radius_km": BUFFER_PREVIEW_RADIUS_KM,
                    "clip_shape": BUFFER_PREVIEW_SHAPE,
                }

        if self.show_treecover:
            lid = f"ca:hansen_tc:{self.treecover_threshold}"
            url = self._url_cache.get(lid)
            if url:
                yield lid, {
                    "id": lid, "url": url, "opacity": self.treecover_opacity,
                    "attribution": layer_service.HANSEN_ATTRIBUTION,
                    "z_index": 11, "max_native_zoom": 15,
                }

        if self.show_forest_age:
            lid = "ca:ntems_age"
            url = self._url_cache.get(lid)
            if url:
                yield lid, {
                    "id": lid, "url": url, "opacity": self.forest_age_opacity,
                    "attribution": layer_service.NTEMS_ATTRIBUTION,
                    "z_index": 12, "max_native_zoom": 15,
                }

        if self.show_change:
            lid = f"ca:hansen_change:{self.change_from_year}:{self.treecover_threshold}"
            url = self._url_cache.get(lid)
            if url:
                yield lid, {
                    "id": lid, "url": url, "opacity": 0.85,
                    "attribution": layer_service.HANSEN_ATTRIBUTION,
                    "z_index": 20, "max_native_zoom": 15,
                }

    def _refresh_layers(self) -> None:
        self.map_layers = self._build_layers()

    # ---------------------------------------------------------------------- #
    # Initialisation
    # ---------------------------------------------------------------------- #

    @rx.event(background=True)
    async def initialise(self):
        """Connect to Earth Engine and paint the base map.

        The base map is seeded synchronously first so the very first frame has
        tiles, then Earth Engine is contacted — the same ordering the Brazil
        page uses so a slow or failed EE connection never leaves a blank map.
        """
        async with self:
            if not self.map_layers:
                self._refresh_layers()
            if self.ee_ready:
                return

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, get_ee)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Earth Engine initialisation failed")
            async with self:
                self.ee_error = str(exc)
            return

        async with self:
            self.ee_ready = True
            self.ee_error = ""
            self._refresh_layers()

        # Warm the magnifier's tile URL now rather than on the first click. It
        # is one call, and paying for it here means the clipped preview appears
        # with the click instead of a second later — which is the whole point of
        # a layer that owes Earth Engine nothing at click time.
        await self._mint(f"ca:aci:{aafc.ACI_YEAR_END}",
                         lambda: layer_service.aci_spec(aafc.ACI_YEAR_END))

    def _set_preview(self, lat: float, lon: float) -> None:
        """Point the magnifier at one location."""
        self.preview_points = [[float(lat), float(lon)]]
        self._refresh_layers()

    def _clear_preview(self) -> None:
        self.preview_points = []
        self._refresh_layers()

    def toggle_buffer_preview(self, checked: bool):
        self.show_buffer_preview = checked
        self._refresh_layers()

    async def _mint(self, layer_id: str, builder) -> None:
        """Mint one tile URL off the event loop and repaint.

        ``builder`` is a zero-argument callable returning a layer spec; it runs
        in the executor because ``getMapId`` is a blocking network call.
        """
        if layer_id in self._url_cache:
            async with self:
                self._refresh_layers()
            return

        async with self:
            self.layer_busy = True
            self._refresh_layers()

        loop = asyncio.get_running_loop()
        try:
            spec = await loop.run_in_executor(None, builder)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Minting %s failed: %s", layer_id, exc)
            spec = None

        async with self:
            self.layer_busy = False
            if spec and spec.get("url"):
                self._url_cache[layer_id] = spec["url"]
            self._refresh_layers()

    # ---------------------------------------------------------------------- #
    # Event handlers
    # ---------------------------------------------------------------------- #

    def set_basemap(self, key: str | list[str]):
        raw = key[0] if isinstance(key, (list, tuple)) and key else key
        if raw in ds.BASEMAPS:
            self.basemap = raw
            self._refresh_layers()

    def set_basemap_by_label(self, label: str):
        """Bridge for the select, which shows labels in the current language."""
        col = "label_pt" if self.language == "pt" else "label_en"
        lookup = {v[col]: k for k, v in ds.BASEMAPS.items()}
        key = lookup.get(label)
        if key:
            self.basemap = key
            self._refresh_layers()

    @rx.event(background=True)
    async def toggle_aci(self, checked: bool):
        async with self:
            self.show_aci = checked
            self._refresh_layers()
            year = self.aci_year
        if checked:
            await self._mint(f"ca:aci:{year}",
                             lambda: layer_service.aci_spec(year))

    @rx.event(background=True)
    async def set_aci_year(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        async with self:
            self.aci_year = int(raw)
            self._refresh_layers()
            year, on = self.aci_year, self.show_aci
        if on:
            await self._mint(f"ca:aci:{year}",
                             lambda: layer_service.aci_spec(year))

    def set_aci_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.aci_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    @rx.event(background=True)
    async def toggle_forest_age(self, checked: bool):
        async with self:
            self.show_forest_age = checked
            self._refresh_layers()
        if checked:
            await self._mint("ca:ntems_age", layer_service.forest_age_spec)

    def set_forest_age_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.forest_age_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    @rx.event(background=True)
    async def toggle_treecover(self, checked: bool):
        async with self:
            self.show_treecover = checked
            self._refresh_layers()
            threshold = self.treecover_threshold
        if checked:
            await self._mint(f"ca:hansen_tc:{threshold}",
                             lambda: layer_service.hansen_treecover_spec(threshold))

    def set_treecover_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.treecover_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    @rx.event(background=True)
    async def toggle_change(self, checked: bool):
        async with self:
            self.show_change = checked
            self._refresh_layers()
            yr, th = self.change_from_year, self.treecover_threshold
        if checked:
            await self._mint(f"ca:hansen_change:{yr}:{th}",
                             lambda: layer_service.hansen_change_spec(yr, th))

    @rx.event(background=True)
    async def set_change_from_year(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        async with self:
            self.change_from_year = int(raw)
            self._refresh_layers()
            yr, th, on = self.change_from_year, self.treecover_threshold, self.show_change
        if on:
            await self._mint(f"ca:hansen_change:{yr}:{th}",
                             lambda: layer_service.hansen_change_spec(yr, th))

    @rx.event(background=True)
    async def set_treecover_threshold(self, value: list[int | float]):
        """The forest definition. Governs both Hansen layers *and* the numbers
        in the change panel, which is why changing it re-runs the analysis."""
        raw = value[0] if isinstance(value, (list, tuple)) else value
        async with self:
            self.treecover_threshold = int(raw)
            self._refresh_layers()
            yr, th = self.change_from_year, self.treecover_threshold
            tc_on, ch_on = self.show_treecover, self.show_change
            lat, lon, has = self.study_lat, self.study_lon, self.has_point
        if tc_on:
            await self._mint(f"ca:hansen_tc:{th}",
                             lambda: layer_service.hansen_treecover_spec(th))
        if ch_on:
            await self._mint(f"ca:hansen_change:{yr}:{th}",
                             lambda: layer_service.hansen_change_spec(yr, th))
        if has:
            return type(self).run_change_only(lat, lon)

    @rx.event(background=True)
    async def toggle_landsat(self, checked: bool):
        async with self:
            self.show_landsat = checked
            self._refresh_layers()
            key, yr = self.landsat_rendering, self.landsat_year
        if checked:
            await self._mint(f"ca:landsat:{key}:{yr}",
                             lambda: layer_service.landsat_spec(key, yr))

    @rx.event(background=True)
    async def set_landsat_year(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        async with self:
            self.landsat_year = int(raw)
            self._refresh_layers()
            key, yr, on = self.landsat_rendering, self.landsat_year, self.show_landsat
        if on:
            await self._mint(f"ca:landsat:{key}:{yr}",
                             lambda: layer_service.landsat_spec(key, yr))

    @rx.event(background=True)
    async def set_landsat_rendering(self, value: str | list[str]):
        raw = value[0] if isinstance(value, (list, tuple)) and value else value
        async with self:
            if raw in ds.LANDSAT_RENDERINGS:
                self.landsat_rendering = raw
            self._refresh_layers()
            key, yr, on = self.landsat_rendering, self.landsat_year, self.show_landsat
        if on:
            await self._mint(f"ca:landsat:{key}:{yr}",
                             lambda: layer_service.landsat_spec(key, yr))

    # ---------------------------------------------------------------------- #
    # Derived display values
    # ---------------------------------------------------------------------- #

    @rx.var
    def basemap_options(self) -> list[str]:
        col = "label_pt" if self.language == "pt" else "label_en"
        return [v[col] for v in ds.BASEMAPS.values()]

    @rx.var
    def basemap_label(self) -> str:
        col = "label_pt" if self.language == "pt" else "label_en"
        return ds.BASEMAPS[self.basemap][col]

    @rx.var
    def landsat_options(self) -> list[str]:
        col = "label_pt" if self.language == "pt" else "label_en"
        return [v[col] for v in ds.LANDSAT_RENDERINGS.values()]

    @rx.var
    def landsat_value(self) -> str:
        col = "label_pt" if self.language == "pt" else "label_en"
        return ds.LANDSAT_RENDERINGS[self.landsat_rendering][col]

    @rx.var
    def landsat_note(self) -> str:
        col = "note_pt" if self.language == "pt" else "note_en"
        return ds.LANDSAT_RENDERINGS[self.landsat_rendering][col]

    @rx.var
    def aci_opacity_pct(self) -> int:
        return int(round(self.aci_opacity * 100))

    @rx.var
    def forest_age_opacity_pct(self) -> int:
        return int(round(self.forest_age_opacity * 100))

    @rx.var
    def treecover_opacity_pct(self) -> int:
        return int(round(self.treecover_opacity * 100))

    @rx.var
    def ee_status_label(self) -> str:
        if self.ee_error:
            return self.tr["status_ee_unavailable"]
        if not self.ee_ready:
            return self.tr["status_ee_connecting"]
        return self.tr["status_ee_ready"]
