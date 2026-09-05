"""Map layer state: basemap, MapBiomas year, opacity, and the layer list.

The layer list is plain state rather than a computed var on purpose. Building it
can require minting Earth Engine tile URLs, and a computed var that makes network
calls would run on every state read — including reads that have nothing to do
with the map.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

import reflex as rx

from ..config import datasets as ds
from ..config import ibge_vegetation as ds_ibge_veg
from ..config import mapbiomas as mb
from ..config import settings as st
from ..services import auto_infracao as auto_infracao_service
from ..services import biomes as biome_service
from ..services import change_mask as cm
from ..services import embargos as embargos_service
from ..services import gbif as gbif_service
from ..services import ifn as ifn_service
from ..services import layers as layer_service
from ..services import territorios as territorio_service
from ..services.biomass import AGB_YEARS

logger = logging.getLogger(__name__)

#: What a select shows for "no filter". Radix selects cannot carry an empty
#: string as a value, so the sentinel is the current language's "All" — everything
#: below :meth:`LayersMixin._unset` speaks the empty-string convention.

#: compare_mode -> (classification side "mb" | "ibge", SPOT basemap key), for
#: the four "classification x SPOT 2008" pairings. MapBiomas or IBGE is
#: whichever classification is being checked; the SPOT year is always 2008
#: (FOREST_CODE_BASELINE_YEAR) because these pairings exist to validate a
#: classification against the Forest Code's own reference-year imagery, not
#: to browse SPOT at an arbitrary year. A module-level constant, not state:
#: it is a fixed lookup table, never mutated per session.
SPOT_COMPARE_SIDES: dict[str, tuple[str, str]] = {
    "mb_spot_visual": ("mb", "spot_2008_visual"),
    "mb_spot_analytic": ("mb", "spot_2008_analytic"),
    "ibge_spot_visual": ("ibge", "spot_2008_visual"),
    "ibge_spot_analytic": ("ibge", "spot_2008_analytic"),
}


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

    #: Swipe comparison, split by a single draggable divider. "years" is two
    #: MapBiomas years; "ibge" is IBGE Vegetação 2022 vs. MapBiomas 2022;
    #: "spot" is the two SPOT 2008 mosaics (Visual vs. false-colour NIR); the
    #: four "*_spot_*" modes validate a classification against the Forest
    #: Code's actual 2008 reference-year imagery (see _SPOT_COMPARE_SIDES and
    #: set_compare_mode). A Literal rather than a pile of booleans that would
    #: only exist to turn each other off: the map has one swipe handle, so
    #: exactly one pairing (or none) can be active, the same way exactly one
    #: basemap is selected at a time.
    compare_mode: Literal[
        "off", "years", "ibge", "spot",
        "mb_spot_visual", "mb_spot_analytic",
        "ibge_spot_visual", "ibge_spot_analytic",
    ] = "off"
    #: Meaningful only for compare_mode == "years" — the two sides carry
    #: independent opacity there (often used to fade one side against the
    #: basemap while keeping the other solid); "ibge" and "spot" reuse
    #: existing opacity settings / have nothing to pick, so they need no
    #: opacity state of their own.
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
    biome_opacity: float = 0.55
    #: Permanent on-map natural_region labels (services.biomes). On by
    #: default — they are only ever visible at zoom >= LABEL_MIN_ZOOM anyway
    #: (leaflet_map.js's applyLabelVisibility), so the default costs nothing
    #: until the user is already zoomed in enough for them to be legible.
    show_biome_labels: bool = True

    # --- Terras indígenas (FUNAI) e unidades de conservação (CNUC/ICMBio) ---
    #: The same kind of layer as the biome overlay above, and for the same
    #: reason: drawn in the browser rather than by Earth Engine so each polygon
    #: can name itself on hover and carry a permanent on-map label. Nothing is
    #: minted for either and nothing here can fail.
    #:
    #: Two toggles sharing one label switch and one opacity. They are read
    #: together — "what protected areas are around this point" is one question,
    #: not two — and four controls where two will do is a worse panel.
    show_terras_indigenas: bool = False
    show_unidades_conservacao: bool = False
    show_territorio_labels: bool = True
    territorio_opacity: float = 0.35

    # --- IBAMA embargos (services.embargos) --------------------------------
    #: A live third-party feed, not Earth Engine — no minting, the browser
    #: fetches it directly (see _build_vectors). Off by default like every
    #: other optional overlay.
    show_embargos: bool = False
    embargos_opacity: float = 0.7

    # --- IBAMA autos de infração (services.auto_infracao) -------------------
    #: Same reasoning as show_embargos — a live third-party feed, no minting.
    show_auto_infracao: bool = False
    auto_infracao_opacity: float = 0.85

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

    # --- IBGE Vegetação 2022 (services.ibge_vegetation) ---------------------
    #: A single 2022 snapshot, not a series, so unlike biomass there is no
    #: year to pick — just a toggle and an opacity slider.
    show_ibge_veg: bool = False
    ibge_veg_opacity: float = 0.6
    #: The leg2_id-level (54-class) breakdown for the study point's buffer —
    #: what the on-map legend's class swatches read from. Distinct from
    #: state._analysis's veg_compare, which reduces the same asset to the
    #: 6-bucket natural/anthropic taxonomy for the QC comparison tab; this
    #: keeps the finer classes a legend actually needs. Populated only when
    #: the layer is toggled on — see toggle_ibge_veg / _run_ibge_veg_history.
    ibge_veg_rows: list[dict[str, Any]] = []
    ibge_veg_busy: bool = False
    ibge_veg_error: str = ""

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

    #: Same, for IBGE vegetation — a single URL, not year-keyed, since there
    #: is only ever one snapshot to mint.
    _ibge_veg_url: str = ""

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
                    # In "years" compare mode the active year takes the RIGHT
                    # half; the baseline year sits underneath on the left.
                    "clip": "right" if self.compare_mode == "years" else None,
                })

            if self.compare_mode == "years":
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

        if self.show_ibge_veg and self._ibge_veg_url:
            specs.append({
                "id": "ibge_vegetation:leg2",
                "url": self._ibge_veg_url,
                "opacity": self.ibge_veg_opacity,
                "attribution": ds_ibge_veg.IBGE_VEG_ATTRIBUTION,
                "z_index": 13,
                "max_native_zoom": 13,
            })

        if self.compare_mode == "ibge":
            # Independent of show_mapbiomas/show_ibge_veg on purpose — both
            # sides are fixed to 2022 (there is nothing to pick), so the
            # curtain does not depend on whichever year the plain MapBiomas
            # layer happens to be showing. z-index above both layers' own
            # (13/10) so this pair always wins if a plain toggle is also on.
            mb_url = self._mb_urls.get(ds_ibge_veg.IBGE_COMPARE_YEAR)
            if mb_url:
                specs.append({
                    "id": f"mapbiomas:{mb.MAPBIOMAS_DEFAULT_COLLECTION}"
                          f":{ds_ibge_veg.IBGE_COMPARE_YEAR}:ibgecmp",
                    "url": mb_url,
                    "opacity": self.mapbiomas_opacity,
                    "attribution": "MapBiomas Collection 10.1",
                    "z_index": 14,
                    "max_native_zoom": 15,
                    "clip": "right",
                })
            if self._ibge_veg_url:
                specs.append({
                    "id": "ibge_vegetation:leg2:cmp",
                    "url": self._ibge_veg_url,
                    "opacity": self.ibge_veg_opacity,
                    "attribution": ds_ibge_veg.IBGE_VEG_ATTRIBUTION,
                    "z_index": 15,
                    "max_native_zoom": 13,
                    "clip": "left",
                })

        elif self.compare_mode == "spot":
            # Same two mosaics offered as mutually-exclusive basemap choices
            # (config.datasets.EE_BASEMAPS) — here shown side by side instead,
            # since both are already circa-2008 SPOT imagery over the same
            # footprint and the only difference is band combination (true
            # colour vs. near-infrared). Independent of `basemap` on purpose,
            # same reasoning as the "ibge" branch above. No opacity slider —
            # both sides are always 1.0, nothing to pick.
            visual_url = self._basemap_urls.get("spot_2008_visual")
            if visual_url:
                specs.append({
                    "id": "basemap:spot_2008_visual:cmp",
                    "url": visual_url,
                    "opacity": 1.0,
                    "attribution": ds.EE_BASEMAPS["spot_2008_visual"]["attribution"],
                    "z_index": 16,
                    "max_native_zoom": ds.EE_BASEMAPS["spot_2008_visual"]
                                       .get("max_native_zoom", 16),
                    "clip": "right",
                })
            analytic_url = self._basemap_urls.get("spot_2008_analytic")
            if analytic_url:
                specs.append({
                    "id": "basemap:spot_2008_analytic:cmp",
                    "url": analytic_url,
                    "opacity": 1.0,
                    "attribution": ds.EE_BASEMAPS["spot_2008_analytic"]["attribution"],
                    "z_index": 17,
                    "max_native_zoom": ds.EE_BASEMAPS["spot_2008_analytic"]
                                       .get("max_native_zoom", 16),
                    "clip": "left",
                })

        elif self.compare_mode in SPOT_COMPARE_SIDES:
            # Validates a classification against the Forest Code's actual
            # 2008 reference-year imagery: MapBiomas 2008 or IBGE Vegetação
            # on the right (whichever is being checked), the chosen SPOT
            # 2008 band on the left. No opacity slider on the SPOT side —
            # same reasoning as "spot" above, nothing to pick.
            side, spot_key = SPOT_COMPARE_SIDES[self.compare_mode]
            if side == "mb":
                mb_url = self._mb_urls.get(cm.FOREST_CODE_BASELINE_YEAR)
                if mb_url:
                    specs.append({
                        "id": f"mapbiomas:{mb.MAPBIOMAS_DEFAULT_COLLECTION}"
                              f":{cm.FOREST_CODE_BASELINE_YEAR}:cmpspot",
                        "url": mb_url,
                        "opacity": self.mapbiomas_opacity,
                        "attribution": "MapBiomas Collection 10.1",
                        "z_index": 16,
                        "max_native_zoom": 15,
                        "clip": "right",
                    })
            else:
                if self._ibge_veg_url:
                    specs.append({
                        "id": "ibge_vegetation:leg2:cmpspot",
                        "url": self._ibge_veg_url,
                        "opacity": self.ibge_veg_opacity,
                        "attribution": ds_ibge_veg.IBGE_VEG_ATTRIBUTION,
                        "z_index": 16,
                        "max_native_zoom": 13,
                        "clip": "right",
                    })
            spot_url = self._basemap_urls.get(spot_key)
            if spot_url:
                spot_conf = ds.EE_BASEMAPS[spot_key]
                specs.append({
                    "id": f"basemap:{spot_key}:cmpref",
                    "url": spot_url,
                    "opacity": 1.0,
                    "attribution": spot_conf["attribution"],
                    "z_index": 17,
                    "max_native_zoom": spot_conf.get("max_native_zoom", 16),
                    "clip": "left",
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
            specs.append(biome_service.vector_spec(
                opacity=self.biome_opacity, show_labels=self.show_biome_labels))
        # Terras indígenas are appended SECOND, and that is what puts them
        # above unidades de conservação where the two overlap, which they do
        # in several hundred places. Every vector shares one Leaflet pane
        # (`nmVectors`, leaflet_map.js) and they are added in the order this
        # list gives them, so stacking is list order; a vector spec's
        # `z_index` is carried for symmetry with the tile specs and orders
        # nothing here. Not arbitrary: there are five times as many unidades
        # de conservação, so the smaller set on top stays findable, and gold
        # on dark purple reads better than the reverse.
        if self.show_unidades_conservacao:
            specs.append(territorio_service.vector_spec(
                "conservacao", opacity=self.territorio_opacity, z_index=6,
                show_labels=self.show_territorio_labels))
        if self.show_terras_indigenas:
            specs.append(territorio_service.vector_spec(
                "indigena", opacity=self.territorio_opacity, z_index=7,
                show_labels=self.show_territorio_labels))
        if self.show_embargos:
            specs.append(embargos_service.vector_spec(opacity=self.embargos_opacity))
        if self.show_auto_infracao:
            specs.append(auto_infracao_service.vector_spec(
                opacity=self.auto_infracao_opacity))
        if self.show_gbif:
            # The only spec here built from live filter state rather than just
            # an opacity — the accordion's whole selection rides in its
            # `query`, and leaflet_map.js's per-layer refetch key includes
            # those params, so changing a filter refetches exactly as a pan
            # does. `emit_meta` asks the map to report the fetch's own counts
            # back (GbifMixin.on_gbif_layer_meta): at zoom 10 a viewport can
            # hold tens of thousands of occurrences against a 300-record page,
            # and the panel has to be able to say so.
            spec = gbif_service.vector_spec(self.gbif_filters,
                                            opacity=self.gbif_opacity)
            spec["emit_meta"] = True
            specs.append(spec)
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
    async def set_compare_mode(self, value: str | list[str]):
        """Which pairing (if any) drives the single swipe divider —
        "years" (two MapBiomas years), "ibge" (IBGE Vegetação 2022 vs.
        MapBiomas 2022), "spot" (the two SPOT 2008 mosaics), or one of the
        four SPOT_COMPARE_SIDES keys (a classification checked against the
        Forest Code's 2008 reference-year imagery). Replaces the old
        toggle_compare/toggle_ibge_compare pair of booleans that only existed
        to turn each other off — this is the mode key itself, not a
        translated label; the select in layer_panel.py goes through
        set_compare_mode_by_label instead, mirroring
        set_basemap/set_basemap_by_label.
        """
        raw = value[0] if isinstance(value, (list, tuple)) and value else value
        mode = str(raw)
        if mode not in ("off", "years", "ibge", "spot", *SPOT_COMPARE_SIDES):
            return

        needed_mb = needed_ibge = needed_visual = needed_analytic = False
        spot_side = spot_key = None
        async with self:
            self.compare_mode = mode
            if mode == "off":
                self._refresh_layers()
                return
            if mode == "years":
                if not self.show_mapbiomas:
                    self.show_mapbiomas = True
                if self.compare_year in self._mb_urls:
                    self._refresh_layers()
                    return
                self.layer_busy = True
            elif mode == "ibge":
                needed_mb = ds_ibge_veg.IBGE_COMPARE_YEAR not in self._mb_urls
                needed_ibge = not self._ibge_veg_url
                if not needed_mb and not needed_ibge:
                    self._refresh_layers()
                    return
                self.layer_busy = True
            elif mode == "spot":
                needed_visual = "spot_2008_visual" not in self._basemap_urls
                needed_analytic = "spot_2008_analytic" not in self._basemap_urls
                if not needed_visual and not needed_analytic:
                    self._refresh_layers()
                    return
                self.layer_busy = True
            elif mode in SPOT_COMPARE_SIDES:
                spot_side, spot_key = SPOT_COMPARE_SIDES[mode]
                if spot_side == "mb":
                    needed_mb = cm.FOREST_CODE_BASELINE_YEAR not in self._mb_urls
                else:
                    needed_ibge = not self._ibge_veg_url
                needed_spot = spot_key not in self._basemap_urls
                if not needed_mb and not needed_ibge and not needed_spot:
                    self._refresh_layers()
                    return
                self.layer_busy = True

        if mode == "years":
            await self._ensure_year(self.compare_year)
            return

        loop = asyncio.get_running_loop()
        if mode == "ibge":
            mb_task = (loop.run_in_executor(
                None, layer_service.mapbiomas_spec, ds_ibge_veg.IBGE_COMPARE_YEAR)
                if needed_mb else None)
            ibge_task = (loop.run_in_executor(None, layer_service.ibge_vegetation_spec)
                         if needed_ibge else None)
            try:
                mb_spec = await mb_task if mb_task else None
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not build MapBiomas %s for IBGE compare: %s",
                               ds_ibge_veg.IBGE_COMPARE_YEAR, exc)
                mb_spec = None
            try:
                ibge_spec = await ibge_task if ibge_task else None
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not build IBGE vegetation layer for compare: %s", exc)
                ibge_spec = None

            async with self:
                if mb_spec:
                    self._mb_urls[ds_ibge_veg.IBGE_COMPARE_YEAR] = mb_spec["url"]
                if ibge_spec:
                    self._ibge_veg_url = ibge_spec["url"]
                self.layer_busy = False
                self._refresh_layers()
            return

        if mode in SPOT_COMPARE_SIDES:
            mb_task = (loop.run_in_executor(
                None, layer_service.mapbiomas_spec, cm.FOREST_CODE_BASELINE_YEAR)
                if needed_mb else None)
            ibge_task = (loop.run_in_executor(None, layer_service.ibge_vegetation_spec)
                         if needed_ibge else None)
            spot_task = (loop.run_in_executor(
                None, layer_service.ee_basemap_spec, spot_key)
                if spot_key and spot_key not in self._basemap_urls else None)
            try:
                mb_spec = await mb_task if mb_task else None
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not build MapBiomas %s for SPOT compare: %s",
                               cm.FOREST_CODE_BASELINE_YEAR, exc)
                mb_spec = None
            try:
                ibge_spec = await ibge_task if ibge_task else None
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not build IBGE vegetation layer for SPOT compare: %s", exc)
                ibge_spec = None
            try:
                spot_spec = await spot_task if spot_task else None
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not build %s for compare: %s", spot_key, exc)
                spot_spec = None

            async with self:
                if mb_spec:
                    self._mb_urls[cm.FOREST_CODE_BASELINE_YEAR] = mb_spec["url"]
                if ibge_spec:
                    self._ibge_veg_url = ibge_spec["url"]
                if spot_spec and spot_key:
                    self._basemap_urls[spot_key] = spot_spec["url"]
                self.layer_busy = False
                self._refresh_layers()
            return

        # mode == "spot"
        visual_task = (loop.run_in_executor(
            None, layer_service.ee_basemap_spec, "spot_2008_visual")
            if needed_visual else None)
        analytic_task = (loop.run_in_executor(
            None, layer_service.ee_basemap_spec, "spot_2008_analytic")
            if needed_analytic else None)
        try:
            visual_spec = await visual_task if visual_task else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not build SPOT 2008 Visual for compare: %s", exc)
            visual_spec = None
        try:
            analytic_spec = await analytic_task if analytic_task else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not build SPOT 2008 Analytic for compare: %s", exc)
            analytic_spec = None

        async with self:
            if visual_spec:
                self._basemap_urls["spot_2008_visual"] = visual_spec["url"]
            if analytic_spec:
                self._basemap_urls["spot_2008_analytic"] = analytic_spec["url"]
            self.layer_busy = False
            self._refresh_layers()

    def set_compare_mode_by_label(self, label: str):
        """Bridge for the select, which shows labels in the current
        language — mirrors set_basemap_by_label."""
        lookup = {
            self.tr["compare_mode_off"]: "off",
            self.tr["compare_mode_years"]: "years",
            self.tr["compare_mode_ibge"]: "ibge",
            self.tr["compare_mode_spot"]: "spot",
            self.tr["compare_mode_mb_spot_visual"]: "mb_spot_visual",
            self.tr["compare_mode_mb_spot_analytic"]: "mb_spot_analytic",
            self.tr["compare_mode_ibge_spot_visual"]: "ibge_spot_visual",
            self.tr["compare_mode_ibge_spot_analytic"]: "ibge_spot_analytic",
        }
        mode = lookup.get(label)
        if mode:
            return type(self).set_compare_mode(mode)

    @rx.event(background=True)
    async def set_compare_year(self, value: list[int | float] | int | str):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        try:
            year = int(raw)
        except (TypeError, ValueError):
            return
        async with self:
            self.compare_year = year
            if self.compare_mode != "years" or year in self._mb_urls:
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
    # IBGE Vegetação 2022
    # ---------------------------------------------------------------------- #

    @rx.event(background=True)
    async def toggle_ibge_veg(self, checked: bool):
        async with self:
            self.show_ibge_veg = checked
            has_point = getattr(self, "has_point", False)
            lat, lon = getattr(self, "study_lat", 0.0), getattr(self, "study_lon", 0.0)
            if not checked or self._ibge_veg_url:
                self._refresh_layers()
            else:
                self.layer_busy = True

        if checked and not self._ibge_veg_url:
            loop = asyncio.get_running_loop()
            try:
                spec = await loop.run_in_executor(None, layer_service.ibge_vegetation_spec)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not build IBGE vegetation layer: %s", exc)
                spec = None

            async with self:
                if spec:
                    self._ibge_veg_url = spec["url"]
                self.layer_busy = False
                self._refresh_layers()

        # The legend's class swatches — only worth fetching once the layer
        # is actually visible, and only if a point exists to scope them to.
        # Deliberately a separate, on-demand computation (also called
        # directly from state._analysis's run_analysis when a new point is
        # picked while this layer is already on) rather than folded into
        # run_analysis's always-on products — most sessions never toggle
        # this layer at all.
        if checked and has_point:
            await self._run_ibge_veg_history(lat, lon)
        elif not checked:
            async with self:
                self.ibge_veg_rows = []

    async def _run_ibge_veg_history(self, lat: float, lon: float) -> None:
        from ..config.settings import BUFFER_MODE_DEFAULT, BUFFER_RADII_KM
        from ..services.geo import point as make_point
        from ..services.ibge_vegetation import veg_history

        async with self:
            self.ibge_veg_busy = True
            self.ibge_veg_error = ""
            shape = getattr(self, "buffer_shape", "circle")

        loop = asyncio.get_running_loop()
        try:
            p = make_point(lat=lat, lon=lon)
            df, _prov = await loop.run_in_executor(
                None, veg_history, p, BUFFER_RADII_KM, BUFFER_MODE_DEFAULT, shape)
        except Exception as exc:                       # noqa: BLE001
            logger.warning("IBGE vegetation legend failed: %s", exc)
            async with self:
                self.ibge_veg_busy = False
                self.ibge_veg_rows = []
                self.ibge_veg_error = self.tr["err_ibge_veg_failed"].format(exc=exc)
            return

        async with self:
            self.ibge_veg_busy = False
            self.ibge_veg_rows = df.to_dict("records") if not df.empty else []

    def set_ibge_veg_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.ibge_veg_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    @rx.var(cache=True, deps=["ibge_veg_rows", "selected_radius", "language"],
            auto_deps=False)
    def ibge_veg_summary_rows(self) -> list[dict[str, Any]]:
        """Top classes at the same radius the main chart shows, for the
        on-map legend — same shape as AnalysisMixin's own summary_rows
        (state._analysis), read from the finer leg2_id-level breakdown
        _run_ibge_veg_history fetches rather than veg_compare's 6 buckets.
        ``selected_radius`` is read via getattr: it lives on AnalysisMixin,
        a sibling mixin invisible to a static checker looking only at this
        class — deps must be explicit here for the same reason as every
        other cross-mixin read in this app (see e.g. camposcope's
        ImovelMixin.disclosure)."""
        radius = getattr(self, "selected_radius", 10.0)
        lang = getattr(self, "language", "pt")
        label_key = "label_en" if lang == "en" else "label_pt"
        rows = [r for r in self.ibge_veg_rows if r.get("radius_km") == radius]
        total = sum(r["area_ha"] for r in rows) or 1.0
        out = [
            {
                "name": r.get(label_key, r.get("label_pt", "")),
                "color": f"#{r['color']}",
                "pct": f"{(r['area_ha'] / total * 100):.1f}%",
            }
            for r in rows
        ]
        out.sort(key=lambda r: r["pct"], reverse=True)
        return out[:8]

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

    def toggle_biome_labels(self, checked: bool):
        """No layer rebuild either — the browser flips a CSS display per
        marker (leaflet_map.js's applyLabelVisibility)."""
        self.show_biome_labels = checked
        self._refresh_layers()

    def set_biome_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.biome_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    def toggle_terras_indigenas(self, checked: bool):
        """No Earth Engine, no minting — same reasoning as toggle_biomes."""
        self.show_terras_indigenas = checked
        self._refresh_layers()

    def toggle_unidades_conservacao(self, checked: bool):
        """No Earth Engine, no minting — same reasoning as toggle_biomes."""
        self.show_unidades_conservacao = checked
        self._refresh_layers()

    def toggle_territorio_labels(self, checked: bool):
        """No layer rebuild either — the browser flips a CSS display per
        marker (leaflet_map.js's applyLabelVisibility)."""
        self.show_territorio_labels = checked
        self._refresh_layers()

    def set_territorio_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.territorio_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    def toggle_embargos(self, checked: bool):
        """No Earth Engine, no minting — same reasoning as toggle_biomes."""
        self.show_embargos = checked
        self._refresh_layers()

    def set_embargos_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.embargos_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    def toggle_auto_infracao(self, checked: bool):
        """No Earth Engine, no minting — same reasoning as toggle_biomes."""
        self.show_auto_infracao = checked
        self._refresh_layers()

    def set_auto_infracao_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.auto_infracao_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    # ---------------------------------------------------------------------- #
    # Derived display values
    # ---------------------------------------------------------------------- #

    @rx.var
    def any_analysis_layer_active(self) -> bool:
        """Whether the on-map legend (components/map_legend.py) has anything
        to show. Unlike camposcope's single tab-driven layer, several of
        these can be on at once, so there is no one boolean already tracking
        this — it is the OR of every independent toggle."""
        return (self.show_mapbiomas or self.show_change_mask
                or self.show_hansen_treecover or self.show_hansen_change
                or self.show_ibge_veg or self.show_biomass
                or self.show_biomes or self.show_ifn or self.show_embargos
                or self.show_auto_infracao or self.show_gbif
                or self.show_terras_indigenas or self.show_unidades_conservacao
                or self.compare_mode != "off")

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
    def compare_mode_label(self) -> str:
        return {
            "off": self.tr["compare_mode_off"],
            "years": self.tr["compare_mode_years"],
            "ibge": self.tr["compare_mode_ibge"],
            "spot": self.tr["compare_mode_spot"],
            "mb_spot_visual": self.tr["compare_mode_mb_spot_visual"],
            "mb_spot_analytic": self.tr["compare_mode_mb_spot_analytic"],
            "ibge_spot_visual": self.tr["compare_mode_ibge_spot_visual"],
            "ibge_spot_analytic": self.tr["compare_mode_ibge_spot_analytic"],
        }.get(self.compare_mode, self.tr["compare_mode_off"])

    @rx.var
    def compare_mode_options(self) -> list[str]:
        # The SPOT-based pairings are dropped entirely when the licence flag
        # is off, same reasoning as ALL_BASEMAPS already applies to the
        # basemap picker: an option that never works is worse than one that
        # is not there.
        options = [self.tr["compare_mode_off"], self.tr["compare_mode_years"],
                   self.tr["compare_mode_ibge"]]
        if st.SPOT_ENABLED:
            options.extend([
                self.tr["compare_mode_spot"],
                self.tr["compare_mode_mb_spot_visual"],
                self.tr["compare_mode_mb_spot_analytic"],
                self.tr["compare_mode_ibge_spot_visual"],
                self.tr["compare_mode_ibge_spot_analytic"],
            ])
        return options

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
    def territorio_opacity_pct(self) -> int:
        return int(round(self.territorio_opacity * 100))

    @rx.var
    def embargos_opacity_pct(self) -> int:
        return int(round(self.embargos_opacity * 100))

    @rx.var
    def auto_infracao_opacity_pct(self) -> int:
        return int(round(self.auto_infracao_opacity * 100))

    @rx.var
    def biomass_opacity_pct(self) -> int:
        return int(round(self.biomass_opacity * 100))

    @rx.var
    def ibge_veg_opacity_pct(self) -> int:
        return int(round(self.ibge_veg_opacity * 100))

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
