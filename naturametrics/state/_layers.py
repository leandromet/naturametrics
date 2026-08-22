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
from ..services import biomes as biome_service
from ..services import change_mask as cm
from ..services import ifn as ifn_service
from ..services import layers as layer_service
from ..services.biomass import AGB_YEARS

logger = logging.getLogger(__name__)

#: What a select shows for "no filter". Radix selects cannot carry an empty
#: string as a value, so the sentinel is the current language's "All" — everything
#: below :meth:`LayersMixin._unset` speaks the empty-string convention.


class LayersMixin(rx.State, mixin=True):
    """Which layers are on the map, and what the map is showing."""

    # --- view -------------------------------------------------------------
    map_center: list[float] = [st.MAP_CENTER[0], st.MAP_CENTER[1]]
    map_zoom: int = st.MAP_ZOOM
    map_bounds: list[list[float]] = [list(st.BRAZIL_VIEW_BOUNDS[0]),
                                     list(st.BRAZIL_VIEW_BOUNDS[1])]

    # --- layer selection --------------------------------------------------
    basemap: str = ds.DEFAULT_BASEMAP
    #: The last plain XYZ basemap chosen. An Earth Engine basemap is drawn *over*
    #: this one rather than instead of it: the SPOT 2008 mosaic covers only
    #: Brazil's forest footprint, so replacing the basemap with it would blank
    #: the rest of the map and read as a broken layer.
    xyz_basemap: str = ds.DEFAULT_BASEMAP
    basemap_error: str = ""
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

    # --- IFN sampling points ----------------------------------------------
    #: The four filters. Empty string means "all" throughout, in the state, the
    #: service and the cache key — one convention, so no layer has to translate.
    show_ifn: bool = False
    ifn_region: str = ""
    ifn_uf: str = ""
    ifn_municipality: str = ""
    ifn_biome: str = ""
    ifn_url: str = ""
    ifn_count: int = ifn_service.count()
    ifn_busy: bool = False

    # --- Buffer land-cover preview ----------------------------------------
    #: MapBiomas shown inside the largest buffer of the hovered or selected
    #: point, and nowhere else. Free: the year's tile URL is already in
    #: ``_mb_urls`` from the startup prefetch, and the restriction to the buffer
    #: is a CSS clip in the browser. Suppressed while the full MapBiomas layer is
    #: on, where it would only redraw what is already everywhere.
    show_buffer_preview: bool = True
    #: The buffers the preview is restricted to, as ``[[lat, lon], …]``. A list
    #: rather than one pair because a multiple selection shows every chosen
    #: conglomerado's buffer at once; the single-point case is a list of one.
    preview_points: list[list[float]] = []

    # --- IBGE biomes ------------------------------------------------------
    #: Drawn in the browser, not by Earth Engine, so that it can name itself on
    #: hover. Nothing is minted for it and nothing here can fail.
    show_biomes: bool = False
    biome_opacity: float = 0.35

    #: Re-applied by the map whenever it changes — how a filter choice frames
    #: itself. Empty list leaves the viewport alone.
    fit_bounds: list[list[float]] = []

    #: Change mask: natural vegetation lost / regrown since the baseline year.
    show_change_mask: bool = False
    change_from_year: int = cm.FOREST_CODE_BASELINE_YEAR
    change_include_stable: bool = False
    change_mask_url: str = ""

    # --- ESA CCI Biomass (services.biomass) --------------------------------
    show_biomass: bool = False
    biomass_year: int = AGB_YEARS[-1]
    biomass_opacity: float = 0.75

    # --- Hansen Global Forest Change, ported from the Canada page ---------
    #: One threshold governs both sub-layers (tree cover 2000, loss/gain), so
    #: it lives outside either toggle rather than under one of them.
    show_hansen_treecover: bool = False
    hansen_treecover_opacity: float = 0.6
    show_hansen_change: bool = False
    hansen_change_opacity: float = 0.85
    hansen_change_from_year: int = ds.HANSEN_GFC["loss_year_start"]
    hansen_treecover_threshold: int = st.HANSEN_TREECOVER_THRESHOLD

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

    #: Vector layer specs — see LeafletMap.vectors. Separate from ``map_layers``
    #: because the browser handles them completely differently: it fetches these
    #: itself instead of being handed a tile URL.
    map_vectors: list[dict[str, Any]] = []

    # --- status -----------------------------------------------------------
    ee_ready: bool = False
    ee_error: str = ""
    layer_busy: bool = False
    prefetch_done: int = 0
    prefetch_total: int = 0

    #: Backend-only cache of year → tile URL. The leading underscore keeps it
    #: out of the browser: 40 signed URLs are not something to ship to a client.
    _mb_urls: dict[int, str] = {}

    #: Same, for Earth-Engine-backed basemaps.
    _basemap_urls: dict[str, str] = {}

    #: Same, for biomass — keyed by year rather than the layer service's own
    #: cache key string, since year is the only thing that varies here.
    _biomass_urls: dict[int, str] = {}

    #: Same, for both Hansen sub-layers — keyed by the layer service's own
    #: cache key string (e.g. "hansen_tc:30", "hansen_change:2015:30") since
    #: two different things vary (threshold; threshold + loss year).
    _hansen_urls: dict[str, str] = {}

    # ---------------------------------------------------------------------- #
    # Layer assembly
    # ---------------------------------------------------------------------- #

    def _build_layers(self) -> list[dict[str, Any]]:
        """Assemble the ordered layer list from current selections."""
        specs: list[dict[str, Any]] = []

        base = layer_service.basemap_spec(self.xyz_basemap, z_index=0)
        if base:
            specs.append(base)

        if ds.is_ee_basemap(self.basemap):
            url = self._basemap_urls.get(self.basemap)
            if url:
                conf = ds.EE_BASEMAPS[self.basemap]
                specs.append({
                    "id": f"basemap:{self.basemap}",
                    "url": url,
                    "opacity": 1.0,
                    "attribution": conf["attribution"],
                    "z_index": 1,
                    "max_native_zoom": conf.get("max_native_zoom", 16),
                })

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

        if (self.show_buffer_preview and self.preview_points
                and not self.show_mapbiomas):
            url = self._mb_urls.get(self.mapbiomas_year)
            if url:
                specs.append({
                    "id": f"preview:{mb.MAPBIOMAS_DEFAULT_COLLECTION}"
                          f":{self.mapbiomas_year}",
                    "url": url,
                    "opacity": st.BUFFER_PREVIEW_OPACITY,
                    "attribution": "MapBiomas Collection 10.1",
                    "z_index": 12,
                    "max_native_zoom": 15,
                    "clip_circles": [{"lat": lat, "lon": lon}
                                     for lat, lon in self.preview_points],
                    "clip_radius_km": st.BUFFER_PREVIEW_RADIUS_KM,
                    "clip_shape": self.buffer_shape,
                })

        if self.show_ifn and self.ifn_url:
            specs.append({
                "id": ifn_service.filter_key(
                    self.ifn_region, self.ifn_uf, self.ifn_municipality,
                    self.ifn_biome),
                "url": self.ifn_url,
                "opacity": 1.0,
                "attribution": ds.IFN_POINTS_JOINED["attribution"],
                # Above everything: the points are the reason the other layers
                # are on screen, and a 3 px dot loses any contest for pixels.
                "z_index": 30,
                "max_native_zoom": 18,
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

        if self.show_biomass:
            url = self._biomass_urls.get(self.biomass_year)
            if url:
                specs.append({
                    "id": f"biomass:{self.biomass_year}",
                    "url": url,
                    "opacity": self.biomass_opacity,
                    "attribution": "ESA CCI Biomass_cci v6.0",
                    "z_index": 14,
                    "max_native_zoom": 13,
                })

        if self.show_hansen_treecover:
            url = self._hansen_urls.get(f"hansen_tc:{self.hansen_treecover_threshold}")
            if url:
                specs.append({
                    "id": f"hansen_tc:{self.hansen_treecover_threshold}",
                    "url": url,
                    "opacity": self.hansen_treecover_opacity,
                    "attribution": ds.HANSEN_GFC["attribution"],
                    "z_index": 15,
                    "max_native_zoom": 13,
                })

        if self.show_hansen_change:
            key = f"hansen_change:{self.hansen_change_from_year}:{self.hansen_treecover_threshold}"
            url = self._hansen_urls.get(key)
            if url:
                specs.append({
                    "id": key,
                    "url": url,
                    "opacity": self.hansen_change_opacity,
                    "attribution": ds.HANSEN_GFC["attribution"],
                    "z_index": 16,
                    "max_native_zoom": 13,
                })
        return specs

    def _refresh_layers(self) -> None:
        self.map_layers = self._build_layers()
        self.map_vectors = self._build_vectors()

    def _build_vectors(self) -> list[dict[str, Any]]:
        """Layers the browser draws itself, in stacking order.

        The conglomerado layer carries the same four filters as its tiles, so the
        clickable points and the drawn points are always the same set — a filter
        that changed one and not the other would be a trap.
        """
        specs: list[dict[str, Any]] = []
        if self.show_biomes:
            specs.append(biome_service.vector_spec(opacity=self.biome_opacity))
        if self.user_points_active:
            # Takes over the interactive layer entirely rather than sitting
            # alongside it — two hoverable point layers stacked in the same
            # pane would fight over which one wins the cursor, and
            # state/_conglomerado.py's hover/click funnel already assumes only
            # one is live at a time.
            specs.append(self.user_points_vector_spec)
        elif self.show_ifn:
            specs.append(ifn_service.vector_spec(
                self.ifn_region, self.ifn_uf, self.ifn_municipality,
                self.ifn_biome, min_zoom=st.IFN_INTERACTIVE_MIN_ZOOM,
            ))
        return specs

    # ---------------------------------------------------------------------- #
    # Event handlers
    # ---------------------------------------------------------------------- #

    @rx.event(background=True)
    async def set_basemap(self, key: str):
        """Swap the basemap. The map instance is untouched, so the view holds.

        Plain XYZ basemaps are a state write and nothing more. The Earth Engine
        ones have to be minted first, which is why this is a background event —
        and why a failure has to put the selection back rather than leave the
        panel claiming a basemap that is not on screen.
        """
        async with self:
            self.basemap_error = ""
            self.basemap = key
            if not ds.is_ee_basemap(key):
                self.xyz_basemap = key
                self._refresh_layers()
                return
            if key in self._basemap_urls:
                self._refresh_layers()
                return
            self.layer_busy = True
            self._refresh_layers()

        loop = asyncio.get_running_loop()
        try:
            spec = await loop.run_in_executor(
                None, layer_service.ee_basemap_spec, key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Basemap %s failed: %s", key, exc)
            spec = None

        async with self:
            self.layer_busy = False
            if spec:
                self._basemap_urls[key] = spec["url"]
            else:
                # Fail closed and say so (doc/04 §2): the SPOT mosaics are
                # licence-gated, and a silent revert would look like a bug in
                # the select rather than a permission the account lacks.
                self.basemap = self.xyz_basemap
                label_key = "label_pt" if self.language == "pt" else "label_en"
                self.basemap_error = self.tr["basemap_unavailable"].format(
                    label=ds.EE_BASEMAPS[key][label_key]
                )
            self._refresh_layers()

    def set_basemap_by_label(self, label: str):
        """Bridge for the select, which shows labels in the current language."""
        key = "label_pt" if self.language == "pt" else "label_en"
        lookup = {v[key]: k for k, v in ds.ALL_BASEMAPS.items()}
        basemap_key = lookup.get(label)
        if basemap_key:
            return type(self).set_basemap(basemap_key)

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
    # ESA CCI Biomass
    # ---------------------------------------------------------------------- #

    @rx.event(background=True)
    async def toggle_biomass(self, checked: bool):
        async with self:
            self.show_biomass = checked
            if not checked:
                self._refresh_layers()
                return
            if self.biomass_year in self._biomass_urls:
                self._refresh_layers()
                return
            self.layer_busy = True
        await self._ensure_biomass_year(self.biomass_year)

    @rx.event(background=True)
    async def set_biomass_year_index(self, value: list[int | float] | int):
        """The slider moves over an index into AGB_YEARS (services.biomass),
        not the year itself — the ten available years are not evenly spaced
        (2007, 2010, then annual from 2015), so a plain min/max/step=1 slider
        over year numbers would let the user land on years that don't exist.
        """
        raw = value[0] if isinstance(value, (list, tuple)) else value
        try:
            index = int(raw)
        except (TypeError, ValueError):
            return
        if not (0 <= index < len(AGB_YEARS)):
            return
        year = AGB_YEARS[index]

        async with self:
            self.biomass_year = year
            if not self.show_biomass or year in self._biomass_urls:
                self._refresh_layers()
                return
            self.layer_busy = True
        await self._ensure_biomass_year(year)

    def set_biomass_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.biomass_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    async def _ensure_biomass_year(self, year: int) -> None:
        loop = asyncio.get_running_loop()
        try:
            spec = await loop.run_in_executor(None, layer_service.biomass_spec, year)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not build biomass %s: %s", year, exc)
            spec = None

        async with self:
            if spec:
                self._biomass_urls[year] = spec["url"]
            self.layer_busy = False
            self._refresh_layers()

    # ---------------------------------------------------------------------- #
    # Hansen Global Forest Change (ported from the Canada page)
    # ---------------------------------------------------------------------- #

    @rx.event(background=True)
    async def toggle_hansen_treecover(self, checked: bool):
        async with self:
            self.show_hansen_treecover = checked
            key = f"hansen_tc:{self.hansen_treecover_threshold}"
            if not checked or key in self._hansen_urls:
                self._refresh_layers()
                return
            self.layer_busy = True
            threshold = self.hansen_treecover_threshold
        await self._ensure_hansen_treecover(threshold)

    @rx.event(background=True)
    async def toggle_hansen_change(self, checked: bool):
        async with self:
            self.show_hansen_change = checked
            key = (f"hansen_change:{self.hansen_change_from_year}:"
                   f"{self.hansen_treecover_threshold}")
            if not checked or key in self._hansen_urls:
                self._refresh_layers()
                return
            self.layer_busy = True
            from_year, threshold = self.hansen_change_from_year, self.hansen_treecover_threshold
        await self._ensure_hansen_change(from_year, threshold)

    @rx.event(background=True)
    async def set_hansen_change_from_year(self, value: list[int | float] | int | str):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        try:
            year = int(raw)
        except (TypeError, ValueError):
            return

        async with self:
            self.hansen_change_from_year = year
            key = f"hansen_change:{year}:{self.hansen_treecover_threshold}"
            if not self.show_hansen_change or key in self._hansen_urls:
                self._refresh_layers()
                return
            self.layer_busy = True
            threshold = self.hansen_treecover_threshold
        await self._ensure_hansen_change(year, threshold)

    @rx.event(background=True)
    async def set_hansen_treecover_threshold(self, value: list[int | float]):
        """Governs both Hansen sub-layers at once — loss is masked by this
        same canopy threshold (services/layers.py::hansen_change_spec), gain
        is not (Hansen publishes it as one undated flag with no canopy % to
        threshold against)."""
        raw = value[0] if isinstance(value, (list, tuple)) else value
        try:
            threshold = int(raw)
        except (TypeError, ValueError):
            return

        async with self:
            self.hansen_treecover_threshold = threshold
            tc_on, ch_on = self.show_hansen_treecover, self.show_hansen_change
            from_year = self.hansen_change_from_year
            # Dropped rather than left pointing at the old threshold's tiles —
            # showing nothing while the new threshold mints is honest; showing
            # the previous threshold's layer would silently answer the wrong
            # question (same reasoning as apply_ifn_filters' stale-URL drop).
            self._refresh_layers()
            if tc_on or ch_on:
                self.layer_busy = True
        if tc_on:
            await self._ensure_hansen_treecover(threshold)
        if ch_on:
            await self._ensure_hansen_change(from_year, threshold)

    def set_hansen_treecover_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.hansen_treecover_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    def set_hansen_change_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.hansen_change_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    async def _ensure_hansen_treecover(self, threshold: int) -> None:
        loop = asyncio.get_running_loop()
        try:
            spec = await loop.run_in_executor(
                None, layer_service.hansen_treecover_spec, threshold)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not build Hansen tree cover %s: %s", threshold, exc)
            spec = None

        async with self:
            if spec:
                self._hansen_urls[spec["id"]] = spec["url"]
            self.layer_busy = False
            self._refresh_layers()

    async def _ensure_hansen_change(self, from_year: int, threshold: int) -> None:
        loop = asyncio.get_running_loop()
        try:
            spec = await loop.run_in_executor(
                None, layer_service.hansen_change_spec, from_year, threshold)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not build Hansen change %s/%s: %s",
                           from_year, threshold, exc)
            spec = None

        async with self:
            if spec:
                self._hansen_urls[spec["id"]] = spec["url"]
            self.layer_busy = False
            self._refresh_layers()

    # ---------------------------------------------------------------------- #
    # IFN points and biomes
    # ---------------------------------------------------------------------- #

    def _set_ifn_filter(self, **changes: str):
        """Apply filter changes and clear whatever they invalidate.

        Cascading downward is not cosmetic. Leaving ``ifn_municipality`` set to a
        Mato Grosso município while the UF moves to Pará produces a filter that
        matches nothing, and an empty map reads as a broken layer rather than as
        a contradictory selection.
        """
        for key, value in changes.items():
            setattr(self, key, value)

        if "ifn_region" in changes:
            # A UF outside the new região, and its município, cannot survive it.
            if self.ifn_uf and ifn_service.region_of(self.ifn_uf) != self.ifn_region:
                self.ifn_uf = ""
                self.ifn_municipality = ""
        if "ifn_uf" in changes:
            self.ifn_municipality = ""
            # Picking a UF directly fills in its região rather than leaving the
            # control above it blank and apparently ignored.
            if self.ifn_uf:
                self.ifn_region = ifn_service.region_of(self.ifn_uf)
        if "ifn_biome" in changes:
            # The biome may exclude the chosen UF entirely (Pampa outside RS) or
            # only the município (a Cerrado município in a Pantanal selection).
            if self.ifn_uf and self.ifn_uf not in ifn_service.uf_options(
                    biome=self.ifn_biome):
                self.ifn_uf = ""
                self.ifn_region = ""
                self.ifn_municipality = ""
            elif self.ifn_municipality and self.ifn_municipality not in (
                    ifn_service.municipality_options(self.ifn_uf, self.ifn_biome)):
                self.ifn_municipality = ""

        return type(self).apply_ifn_filters

    @rx.event(background=True)
    async def apply_ifn_filters(self):
        """Recount, reframe, and re-mint the point layer for the current filter.

        The count and the extent come from the local index and are set before any
        Earth Engine work starts, so the panel and the viewport respond
        immediately even when the tiles take a moment.
        """
        async with self:
            region, uf = self.ifn_region, self.ifn_uf
            municipality, biome = self.ifn_municipality, self.ifn_biome
            self.ifn_count = ifn_service.count(region, uf, municipality, biome)
            self.fit_bounds = ifn_service.extent(
                region, uf, municipality, biome) or []
            if not self.show_ifn:
                self.ifn_url = ""
                self._refresh_layers()
                return
            # Drop the stale URL first: keeping the previous filter's points on
            # screen while the new ones mint shows the user the wrong answer to
            # the question they just asked.
            self.ifn_url = ""
            self.ifn_busy = True
            self._refresh_layers()

        loop = asyncio.get_running_loop()
        try:
            spec = await loop.run_in_executor(
                None, ifn_service.points_spec, region, uf, municipality, biome
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("IFN layer failed for %s: %s", ifn_service.filter_key(
                region, uf, municipality, biome), exc)
            spec = None

        async with self:
            # Discard a result the user has already filtered away — the executor
            # returns in completion order, not request order.
            if (region, uf, municipality, biome) != (
                    self.ifn_region, self.ifn_uf, self.ifn_municipality,
                    self.ifn_biome):
                return
            self.ifn_url = spec["url"] if spec else ""
            self.ifn_busy = False
            self._refresh_layers()

    def toggle_ifn(self, checked: bool):
        self.show_ifn = checked
        if not checked:
            self.ifn_url = ""
            self._refresh_layers()
            return
        return type(self).apply_ifn_filters

    def _unset(self, value: str) -> str:
        return "" if value == self.tr["filter_all"] else value

    def set_ifn_region(self, value: str):
        return self._set_ifn_filter(ifn_region=self._unset(value))

    def set_ifn_uf(self, value: str):
        return self._set_ifn_filter(ifn_uf=self._unset(value))

    def set_ifn_municipality(self, value: str):
        return self._set_ifn_filter(ifn_municipality=self._unset(value))

    def set_ifn_biome(self, value: str):
        return self._set_ifn_filter(ifn_biome=self._unset(value))

    def clear_ifn_filters(self):
        self.ifn_region = ""
        self.ifn_uf = ""
        self.ifn_municipality = ""
        self.ifn_biome = ""
        return type(self).apply_ifn_filters

    def _set_preview(self, lat: float, lon: float) -> None:
        """Point the land-cover preview at one location."""
        self._set_preview_many([[float(lat), float(lon)]])

    def _set_preview_many(self, points: list[list[float]]) -> None:
        """Restrict the preview to several buffers at once."""
        self.preview_points = [[float(lat), float(lon)] for lat, lon in points]
        self._refresh_layers()

    def _clear_preview(self) -> None:
        self.preview_points = []
        self._refresh_layers()

    def toggle_buffer_preview(self, checked: bool):
        self.show_buffer_preview = checked
        self._refresh_layers()

    def toggle_biomes(self, checked: bool):
        """No Earth Engine, no minting — the browser fetches the polygons itself."""
        self.show_biomes = checked
        self._refresh_layers()

    def set_biome_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.biome_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    # ---------------------------------------------------------------------- #
    # Derived display values
    # ---------------------------------------------------------------------- #

    @rx.var
    def basemap_label(self) -> str:
        key = "label_pt" if self.language == "pt" else "label_en"
        return ds.ALL_BASEMAPS[self.basemap][key]

    @rx.var
    def basemap_options(self) -> list[str]:
        key = "label_pt" if self.language == "pt" else "label_en"
        return [v[key] for v in ds.ALL_BASEMAPS.values()]

    @rx.var
    def basemap_note(self) -> str:
        if self.basemap not in ds.EE_BASEMAPS:
            return ""
        key = "note_pt" if self.language == "pt" else "note_en"
        return ds.EE_BASEMAPS[self.basemap].get(key, "")

    @rx.var
    def opacity_pct(self) -> int:
        return int(round(self.mapbiomas_opacity * 100))

    @rx.var
    def compare_opacity_pct(self) -> int:
        return int(round(self.compare_opacity * 100))

    @rx.var
    def ee_status_label(self) -> str:
        if self.ee_error:
            return self.tr["status_ee_unavailable"]
        if not self.ee_ready:
            return self.tr["status_ee_connecting"]
        if self.prefetch_total and self.prefetch_done < self.prefetch_total:
            return self.tr["status_ee_prefetching"].format(
                done=self.prefetch_done, total=self.prefetch_total)
        return self.tr["status_ee_ready"].format(done=self.prefetch_done)

    @rx.var
    def biome_opacity_pct(self) -> int:
        return int(round(self.biome_opacity * 100))

    @rx.var
    def biomass_opacity_pct(self) -> int:
        return int(round(self.biomass_opacity * 100))

    @rx.var
    def hansen_treecover_opacity_pct(self) -> int:
        return int(round(self.hansen_treecover_opacity * 100))

    @rx.var
    def hansen_change_opacity_pct(self) -> int:
        return int(round(self.hansen_change_opacity * 100))

    # --- IFN filter options ------------------------------------------------
    # Computed rather than stored: the full município table is 4 100 names and
    # only the list for the selected UF has any business reaching the browser.
    #: ``tr["filter_all"]`` stands in for "no filter" because a Radix select
    #: cannot hold an empty-string value — it treats it as nothing selected and
    #: shows the placeholder, so clearing a filter would leave the control blank.

    @rx.var
    def ifn_region_options(self) -> list[str]:
        return [self.tr["filter_all"], *ifn_service.options()["regions"]]

    @rx.var
    def ifn_uf_options(self) -> list[str]:
        return [self.tr["filter_all"],
                *ifn_service.uf_options(self.ifn_region, self.ifn_biome)]

    @rx.var
    def ifn_municipality_options(self) -> list[str]:
        return [self.tr["filter_all"], *ifn_service.municipality_options(
            self.ifn_uf, self.ifn_biome)]

    @rx.var
    def ifn_biome_options(self) -> list[str]:
        return [self.tr["filter_all"], *ifn_service.biome_options(self.ifn_uf)]

    @rx.var
    def ifn_region_value(self) -> str:
        return self.ifn_region or self.tr["filter_all"]

    @rx.var
    def ifn_uf_value(self) -> str:
        return self.ifn_uf or self.tr["filter_all"]

    @rx.var
    def ifn_municipality_value(self) -> str:
        return self.ifn_municipality or self.tr["filter_all"]

    @rx.var
    def ifn_biome_value(self) -> str:
        return self.ifn_biome or self.tr["filter_all"]

    @rx.var
    def ifn_has_filter(self) -> bool:
        return bool(self.ifn_region or self.ifn_uf or self.ifn_municipality
                    or self.ifn_biome)

    @rx.var
    def ifn_count_label(self) -> str:
        """e.g. "1.817 conglomerados" / "1,817 clusters"."""
        n = f"{self.ifn_count:,}"
        if self.language == "pt":
            n = n.replace(",", ".")
        noun = self.tr["ifn_count_label_one" if self.ifn_count == 1
                        else "ifn_count_label_many"]
        return f"{n} {noun}"

    @rx.var
    def ifn_municipality_hint(self) -> str:
        return (self.tr["ifn_municipality_hint"] if not self.ifn_uf else "")
