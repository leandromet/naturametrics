"""GBIF occurrences for the Canada page: the layer toggle, the ALA-style filter
accordion, and the species-in-buffer analysis.

Ported from the Brazil page's ``state/_gbif.py`` (``GbifMixin``) feature-for-
feature — same cascade, same filters, same buffer analysis — with the country
swapped from BR to CA and ``self.lang``/``AppState`` swapped for
``self.language``/``CanadaState``. Point tracking is not reinvented: this
mixin reads ``has_point``/``study_lat``/``study_lon`` straight off
``CanadaPointMixin`` (``canada/state/_point.py``).

Three of the five backing modules are the Brazil page's own, imported
directly rather than duplicated: ``gbif_taxa`` (the backbone lookups take no
country parameter at all) and ``gbif_buffers`` (purely lat/lon/radius/
``Filters``-driven — it never looks at which ``Filters`` subclass produced the
object, only calls ``.as_params()`` on it). The three row models
(``GbifSpeciesRow``/``GbifKingdomRow``/``GbifBufferRow``) are plain pydantic
models with no country-specific fields either, so they are imported from the
Brazil state module rather than redefined. Only ``services/gbif.py`` (country
+ GADM table) and ``services/gbif_export.py`` (Portuguese vs. English
spreadsheet text) have real Canada-side copies.
"""

from __future__ import annotations

import logging
from typing import Any

import reflex as rx

from ...config.settings import (
    BUFFER_RADII_KM,
    GBIF_MIN_ZOOM,
    GBIF_SPECIES_TABLE_LIMIT,
)
from ...services import gbif_buffers, gbif_taxa
from ...state._gbif import GbifBufferRow, GbifKingdomRow, GbifSpeciesRow
from ..config import gbif as gc
from ..services import gbif as gbif_service
from ..services import gbif_export

logger = logging.getLogger(__name__)

_ANY = "—"

_LEVELS: tuple[tuple[str, str], ...] = (
    ("KINGDOM", "kingdom"),
    ("PHYLUM", "phylum"),
    ("CLASS", "class_"),
    ("ORDER", "order"),
    ("FAMILY", "family"),
    ("GENUS", "genus"),
    ("SPECIES", "species"),
)


class CanadaGbifMixin(rx.State, mixin=True):
    """GBIF layer state for the Canada page."""

    # --- layer ------------------------------------------------------------
    show_gbif: bool = False
    gbif_opacity: float = 0.85

    # --- the taxonomic cascade -------------------------------------------
    gbif_kingdom: str = ""
    gbif_phylum: str = ""
    gbif_class_: str = ""
    gbif_order: str = ""
    gbif_family: str = ""
    gbif_genus: str = ""
    gbif_species: str = ""

    gbif_kingdom_options: list[str] = [_ANY] + [n for _k, n in gc.KINGDOMS]
    gbif_phylum_options: list[str] = [_ANY]
    gbif_class__options: list[str] = [_ANY]
    gbif_order_options: list[str] = [_ANY]
    gbif_family_options: list[str] = [_ANY]
    gbif_genus_options: list[str] = [_ANY]
    gbif_species_options: list[str] = [_ANY]

    _gbif_keys: dict[str, int] = {}

    gbif_taxa_busy: bool = False

    # --- the other filters ------------------------------------------------
    gbif_basis: list[str] = []
    gbif_year_from: int = 0
    gbif_year_to: int = 0
    #: A province/territory GADM gid — named "province" rather than the
    #: Brazil page's "uf", the term this app's Canada side already uses
    #: nowhere else, so there was no existing convention to collide with.
    gbif_province: str = ""
    gbif_name_query: str = ""
    gbif_name_suggestions: list[dict[str, str]] = []
    gbif_name_busy: bool = False

    # --- what the layer reported back ------------------------------------
    gbif_in_view: int = 0
    gbif_shown: int = 0
    gbif_truncated: bool = False
    gbif_layer_error: str = ""

    # --- species in the buffers ------------------------------------------
    gbif_buffer_rows: list[GbifBufferRow] = []
    gbif_buffer_busy: bool = False
    gbif_buffer_error: str = ""
    gbif_export_error: str = ""

    # ---------------------------------------------------------------------- #
    # Layer toggle
    # ---------------------------------------------------------------------- #
    def toggle_gbif(self, checked: bool):
        self.show_gbif = checked
        if not checked:
            self.gbif_in_view = 0
            self.gbif_shown = 0
            self.gbif_truncated = False
            self.gbif_layer_error = ""
        self._refresh_layers()

    def set_gbif_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.gbif_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    def on_gbif_layer_meta(self, meta: dict):
        """Filters on the layer id, same reasoning as the Brazil page's
        handler: shared by every layer that sets ``emit_meta``."""
        if (meta or {}).get("id") != "ca:gbif_occurrences":
            return
        self.gbif_in_view = int(meta.get("count") or 0)
        self.gbif_shown = int(meta.get("shown") or 0)
        self.gbif_truncated = bool(meta.get("truncated"))
        self.gbif_layer_error = str(meta.get("error") or "")

    # ---------------------------------------------------------------------- #
    # The cascade
    # ---------------------------------------------------------------------- #
    def _level_index(self, suffix: str) -> int:
        for i, (_rank, name) in enumerate(_LEVELS):
            if name == suffix:
                return i
        return -1

    def _clear_below(self, index: int) -> None:
        for _rank, suffix in _LEVELS[index + 1:]:
            setattr(self, f"gbif_{suffix}", "")
            setattr(self, f"gbif_{suffix}_options", [_ANY])

    @rx.event(background=True)
    async def load_gbif_children(self, parent_key: int, index: int):
        if index + 1 >= len(_LEVELS):
            return
        rank, suffix = _LEVELS[index + 1]

        async with self:
            self.gbif_taxa_busy = True
        try:
            rows = gbif_taxa.children(parent_key, rank)
        finally:
            async with self:
                self.gbif_taxa_busy = False
                keys = dict(self._gbif_keys)
                for row in rows:
                    keys[f"{rank}:{row['name']}"] = row["key"]
                self._gbif_keys = keys
                setattr(self, f"gbif_{suffix}_options",
                        [_ANY] + [r["name"] for r in rows])

    def _select_level(self, suffix: str, value: str):
        index = self._level_index(suffix)
        if index < 0:
            return None
        chosen = "" if value == _ANY else value
        setattr(self, f"gbif_{suffix}", chosen)
        self._clear_below(index)
        self._clear_name_search()
        self._refresh_layers()
        if not chosen:
            return None
        rank = _LEVELS[index][0]
        key = self._gbif_keys.get(f"{rank}:{chosen}")
        # type(self), not CanadaGbifMixin — Reflex materialises EventHandler
        # objects only on the concrete state; see the Brazil mixin's own
        # comment on this exact line.
        return None if key is None else type(self).load_gbif_children(key, index)

    def set_gbif_kingdom(self, value: str):
        return self._select_level("kingdom", value)

    def set_gbif_phylum(self, value: str):
        return self._select_level("phylum", value)

    def set_gbif_class(self, value: str):
        return self._select_level("class_", value)

    def set_gbif_order(self, value: str):
        return self._select_level("order", value)

    def set_gbif_family(self, value: str):
        return self._select_level("family", value)

    def set_gbif_genus(self, value: str):
        return self._select_level("genus", value)

    def set_gbif_species(self, value: str):
        return self._select_level("species", value)

    # ---------------------------------------------------------------------- #
    # Free-text name search
    # ---------------------------------------------------------------------- #
    def _clear_name_search(self) -> None:
        self.gbif_name_query = ""
        self.gbif_name_suggestions = []

    @rx.event(background=True)
    async def set_gbif_name_query(self, value: str):
        async with self:
            self.gbif_name_query = value
            if len((value or "").strip()) < 3:
                self.gbif_name_suggestions = []
                return
            self.gbif_name_busy = True
        try:
            rows = gbif_taxa.suggest(value)
        finally:
            async with self:
                self.gbif_name_busy = False
                if self.gbif_name_query == value:
                    self.gbif_name_suggestions = [
                        {"key": str(r["key"]), "name": r["name"],
                         "rank": str(r["rank"] or "").title(),
                         "context": r["context"]}
                        for r in rows
                    ]

    def choose_gbif_suggestion(self, key: str, name: str):
        for _rank, suffix in _LEVELS:
            setattr(self, f"gbif_{suffix}", "")
            if suffix != "kingdom":
                setattr(self, f"gbif_{suffix}_options", [_ANY])
        self.gbif_name_query = name
        self.gbif_name_suggestions = []
        keys = dict(self._gbif_keys)
        keys[f"NAME:{name}"] = int(key)
        self._gbif_keys = keys
        self._refresh_layers()

    # ---------------------------------------------------------------------- #
    # The remaining filters
    # ---------------------------------------------------------------------- #
    def toggle_gbif_basis(self, code: str, checked: bool):
        current = [b for b in self.gbif_basis if b != code]
        if checked:
            current.append(code)
        self.gbif_basis = current
        self._refresh_layers()

    def set_gbif_years(self, value: list[int | float]):
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            return
        lo, hi = int(value[0]), int(value[1])
        if lo <= gc.YEAR_MIN and hi >= self._year_now:
            self.gbif_year_from = 0
            self.gbif_year_to = 0
        else:
            self.gbif_year_from = lo
            self.gbif_year_to = hi
        self._refresh_layers()

    def set_gbif_province(self, value: str):
        self.gbif_province = "" if value == _ANY else value
        self._refresh_layers()

    def clear_gbif_filters(self):
        for _rank, suffix in _LEVELS:
            setattr(self, f"gbif_{suffix}", "")
            if suffix != "kingdom":
                setattr(self, f"gbif_{suffix}_options", [_ANY])
        self._clear_name_search()
        self.gbif_basis = []
        self.gbif_year_from = 0
        self.gbif_year_to = 0
        self.gbif_province = ""
        self._refresh_layers()

    # ---------------------------------------------------------------------- #
    # Derived
    # ---------------------------------------------------------------------- #
    @property
    def _year_now(self) -> int:
        import time
        return time.gmtime().tm_year

    @property
    def gbif_taxon_key(self) -> int:
        name_key = self._gbif_keys.get(f"NAME:{self.gbif_name_query}")
        if name_key:
            return name_key
        for rank, suffix in reversed(_LEVELS):
            chosen = getattr(self, f"gbif_{suffix}", "")
            if chosen:
                key = self._gbif_keys.get(f"{rank}:{chosen}")
                if key:
                    return key
        return 0

    @property
    def gbif_filters(self) -> gbif_service.Filters:
        province_gid = ""
        if self.gbif_province:
            province_gid = next((gid for gid, code, _name in gc.PROVINCE_GADM
                                 if code == self.gbif_province), "")
        return gbif_service.Filters(
            taxon_key=self.gbif_taxon_key or None,
            basis_of_record=tuple(self.gbif_basis),
            year_from=self.gbif_year_from or None,
            year_to=self.gbif_year_to or None,
            gadm_gid=province_gid,
        )

    @rx.var
    def gbif_opacity_pct(self) -> int:
        return int(round(self.gbif_opacity * 100))

    @rx.var
    def gbif_province_options(self) -> list[str]:
        return [_ANY] + [code for _gid, code, _name in gc.PROVINCE_GADM]

    @rx.var
    def gbif_province_value(self) -> str:
        return self.gbif_province or _ANY

    @rx.var
    def gbif_has_filter(self) -> bool:
        return bool(self.gbif_taxon_key or self.gbif_basis or self.gbif_year_from
                    or self.gbif_year_to or self.gbif_province)

    @rx.var
    def gbif_taxon_label(self) -> str:
        if self.gbif_name_query and self._gbif_keys.get(
                f"NAME:{self.gbif_name_query}"):
            return self.gbif_name_query
        for _rank, suffix in reversed(_LEVELS):
            chosen = getattr(self, f"gbif_{suffix}", "")
            if chosen:
                return chosen
        return ""

    @rx.var
    def gbif_year_label(self) -> str:
        if not (self.gbif_year_from or self.gbif_year_to):
            return ""
        return f"{self.gbif_year_from}–{self.gbif_year_to}"

    @rx.var
    def gbif_min_zoom(self) -> int:
        return GBIF_MIN_ZOOM

    @rx.var
    def gbif_view_label(self) -> str:
        if not self.gbif_truncated or not self.gbif_in_view:
            return ""
        return f"{self.gbif_shown:,}/{self.gbif_in_view:,}".replace(",", " ")

    # ---------------------------------------------------------------------- #
    # Species in the buffers
    # ---------------------------------------------------------------------- #
    @rx.event(background=True)
    async def run_gbif_buffers(self):
        """Species recorded inside each buffer around the current study point.

        Fans out through the Brazil page's own ``services/gbif_buffers.py`` —
        reused directly, not re-implemented, since it is driven entirely by
        lat/lon/radii and the ``Filters`` object passed in (its
        ``.as_params()`` call does not care which page built it).
        """
        async with self:
            if not self.has_point:
                self.gbif_buffer_rows = []
                return
            lat, lon = self.study_lat, self.study_lon
            filters = self.gbif_filters
            self.gbif_buffer_busy = True
            self.gbif_buffer_error = ""

        try:
            rows = gbif_buffers.species_by_buffer(lat, lon, BUFFER_RADII_KM,
                                                  filters)
        except Exception as exc:  # noqa: BLE001
            logger.exception("GBIF CA buffer analysis failed")
            async with self:
                self.gbif_buffer_busy = False
                self.gbif_buffer_error = str(exc)
            return

        async with self:
            self.gbif_buffer_busy = False
            self.gbif_buffer_error = next((r.error for r in rows if r.error), "")
            self.gbif_buffer_rows = [
                GbifBufferRow(
                    radius_km=r.radius_km,
                    radius_label=f"{r.radius_km:g} km",
                    total=r.total,
                    total_label=f"{r.total:,}".replace(",", " "),
                    richness=r.richness,
                    richness_label=(f"{r.richness}+" if r.richness_truncated
                                    else str(r.richness)),
                    species=(species := [
                        GbifSpeciesRow(name=n, count=c,
                                       count_label=f"{c:,}".replace(",", " "))
                        for n, c in r.species
                    ]),
                    species_top=species[:GBIF_SPECIES_TABLE_LIMIT],
                    kingdoms=[GbifKingdomRow(name=n, count=c)
                              for n, c in r.kingdoms],
                    error=r.error,
                )
                for r in rows
            ]

    # ---------------------------------------------------------------------- #
    # Export
    # ---------------------------------------------------------------------- #
    def _gbif_export_context(self) -> list[list[Any]]:
        """Where the point was. Slimmer than the Brazil page's own version:
        CanadaPointMixin does not carry a reverse-geocoded municipality,
        province or biome the way the Brazil page's PointMixin does, so there
        is nothing to add beyond the coordinates and the click label."""
        return [
            ["  latitude", round(self.study_lat, 6)],
            ["  longitude", round(self.study_lon, 6)],
            ["  label", self.point_label or "—"],
        ]

    def _gbif_export_filters(self) -> list[list[str]]:
        out: list[list[str]] = []
        if self.gbif_taxon_label:
            out.append(["  taxon", self.gbif_taxon_label])
        if self.gbif_basis:
            labels = {code: en for code, _pt, en in gc.BASIS_OF_RECORD}
            out.append(["  basis of record",
                        ", ".join(labels.get(b, b) for b in self.gbif_basis)])
        if self.gbif_year_from or self.gbif_year_to:
            out.append(["  event year", self.gbif_year_label])
        if self.gbif_province:
            out.append(["  province/territory", self.gbif_province])
        return out

    def download_gbif_species_ods(self):
        if not self.gbif_buffer_rows:
            self.gbif_export_error = self.tr["gbif_export_nothing"]
            return None
        self.gbif_export_error = ""
        try:
            data, name = gbif_export.build_ods(
                self.gbif_buffer_rows,
                self._gbif_export_context(),
                self._gbif_export_filters(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("GBIF CA species ODS export failed")
            self.gbif_export_error = str(exc)
            return None
        return rx.download(data=data, filename=name,
                           mime_type=gbif_export.MIMETYPE)

    def download_gbif_species_csv(self):
        if not self.gbif_buffer_rows:
            self.gbif_export_error = self.tr["gbif_export_nothing"]
            return None
        self.gbif_export_error = ""
        data, name = gbif_export.build_csv(self.gbif_buffer_rows)
        return rx.download(data=data, filename=name, mime_type="text/csv")
