"""GBIF occurrences: the layer toggle, the ALA-style filter accordion, and the
species-in-buffer analysis.

Its own mixin rather than more of ``_layers.py`` because it carries far more
state than any other overlay — the IBAMA layers are a boolean and an opacity
each, this one is a seven-level taxonomic cascade plus four other filters plus
an analysis result set. It follows ``_conglomerado.py``'s precedent: a layer
whose *filters* are the feature gets its own file.

**The cascade is the interesting part.** Each rank's dropdown is populated from
the GBIF backbone children of whatever was chosen one level up, so choosing
"Chordata" leaves the class dropdown holding 16 real options rather than every
class in the kingdom. Selecting at any level narrows the map immediately — the
effective ``taxonKey`` is simply the deepest selection, so nobody has to walk
all seven levels to filter by "birds".

Every backbone lookup is a cached in-process call (services/gbif_taxa.py), so
opening a dropdown costs nothing after the first time. The only network traffic
that scales with use is the occurrence fetch itself, and that is gated behind
zoom 10.
"""

from __future__ import annotations

import logging
from typing import Any

import reflex as rx
from pydantic import BaseModel

from ..config import gbif as gc
from ..config.settings import BUFFER_RADII_KM, GBIF_MIN_ZOOM
from ..services import gbif as gbif_service
from ..services import gbif_buffers, gbif_taxa

logger = logging.getLogger(__name__)

#: Blank option for every filter dropdown. rx.select cannot hold an empty
#: string as a real value, so "no filter" needs a visible sentinel — the same
#: device _layers.py uses for the IFN filters.
_ANY = "—"

class GbifSpeciesRow(BaseModel):
    """One species line under a buffer.

    A typed model rather than a plain dict: Reflex cannot ``foreach`` over a
    ``list[dict[str, Any]]`` — the value type is untyped, so it has no way to
    know what ``row["species"]`` is, and tests/test_app_builds.py fails the
    page build rather than letting it reach the browser broken.

    ``pydantic.BaseModel`` rather than ``rx.Base``, which Reflex deprecated in
    0.8.15 and removes in 0.9 — pydantic is already a direct dependency
    (requirements.txt), so this costs nothing and does not need revisiting at
    the next upgrade.
    """

    name: str
    count: int
    count_label: str


class GbifKingdomRow(BaseModel):
    name: str
    count: int


class GbifBufferRow(BaseModel):
    """One buffer radius' biodiversity summary, ready to render."""

    radius_km: float
    radius_label: str
    total: int
    total_label: str
    richness: int
    richness_label: str
    species: list[GbifSpeciesRow]
    kingdoms: list[GbifKingdomRow]
    error: str


#: The cascade, as (rank, state-var suffix) in order. Kept as data rather than
#: seven copies of the same handler: every level behaves identically except for
#: which ranks it clears below it.
_LEVELS: tuple[tuple[str, str], ...] = (
    ("KINGDOM", "kingdom"),
    ("PHYLUM", "phylum"),
    ("CLASS", "class_"),
    ("ORDER", "order"),
    ("FAMILY", "family"),
    ("GENUS", "genus"),
    ("SPECIES", "species"),
)


class GbifMixin(rx.State, mixin=True):
    """GBIF layer state."""

    # --- layer ------------------------------------------------------------
    #: A live third-party feed, not Earth Engine — nothing is minted, and the
    #: browser fetches it. Off by default like every other optional overlay.
    show_gbif: bool = False
    gbif_opacity: float = 0.85

    # --- the taxonomic cascade -------------------------------------------
    #: The selected NAME at each rank ("" = nothing chosen). Names rather than
    #: keys because rx.select works in strings and the label is what the user
    #: picked; the key is looked up from _gbif_keys below.
    gbif_kingdom: str = ""
    gbif_phylum: str = ""
    gbif_class_: str = ""
    gbif_order: str = ""
    gbif_family: str = ""
    gbif_genus: str = ""
    gbif_species: str = ""

    #: Options for each rank, refreshed when the level above it changes.
    #: Kingdom's list is fixed (config.gbif.KINGDOMS) so it is seeded here.
    gbif_kingdom_options: list[str] = [_ANY] + [n for _k, n in gc.KINGDOMS]
    gbif_phylum_options: list[str] = [_ANY]
    gbif_class__options: list[str] = [_ANY]
    gbif_order_options: list[str] = [_ANY]
    gbif_family_options: list[str] = [_ANY]
    gbif_genus_options: list[str] = [_ANY]
    gbif_species_options: list[str] = [_ANY]

    #: ``"rank:name" -> backbone key``. A backend-only var (leading underscore):
    #: it is bookkeeping for resolving a dropdown label to the taxonKey the API
    #: needs, and has no business being serialised to the browser on every
    #: state delta.
    _gbif_keys: dict[str, int] = {}

    gbif_taxa_busy: bool = False

    # --- the other filters ------------------------------------------------
    gbif_basis: list[str] = []
    gbif_year_from: int = 0
    gbif_year_to: int = 0
    gbif_uf: str = ""
    #: Free-text name search, resolved to a backbone key through the suggestion
    #: list rather than sent as text — see ``choose_gbif_suggestion``.
    gbif_name_query: str = ""
    gbif_name_suggestions: list[dict[str, str]] = []
    gbif_name_busy: bool = False

    # --- what the layer reported back ------------------------------------
    #: Straight from the FeatureCollection's own properties, via the map's
    #: ``on_layer_meta``. ``gbif_in_view`` is what the API said matched the
    #: viewport; ``gbif_shown`` is how many of those actually came back.
    gbif_in_view: int = 0
    gbif_shown: int = 0
    gbif_truncated: bool = False
    gbif_layer_error: str = ""

    # --- species in the buffers ------------------------------------------
    #: One row per buffer radius, smallest first. ``rx.Base`` models rather
    #: than the service's dataclass — Reflex state has to be serialisable, and
    #: rather than plain dicts because the component ``foreach``es over them
    #: and over their nested species lists.
    gbif_buffer_rows: list[GbifBufferRow] = []
    gbif_buffer_busy: bool = False
    gbif_buffer_error: str = ""

    # ---------------------------------------------------------------------- #
    # Layer toggle
    # ---------------------------------------------------------------------- #
    def toggle_gbif(self, checked: bool):
        """No Earth Engine, no minting — same reasoning as toggle_biomes."""
        self.show_gbif = checked
        if not checked:
            # Otherwise a re-enabled layer briefly shows the previous view's
            # count while its first fetch is still in flight.
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
        """Receive one dynamic layer's fetch report from the map.

        Shared by every layer that sets ``emit_meta``, so it filters on the id
        rather than assuming it is the GBIF one — today it is, and a silent
        mix-up later would be very hard to see.
        """
        if (meta or {}).get("id") != "gbif_occurrences":
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
        """Blank every rank below ``index`` and empty its options.

        Required, not tidiness: the class list under Chordata is meaningless
        once the phylum changes to Arthropoda, and leaving "Aves" selected
        would keep filtering the map by a taxon no longer reachable from the
        chosen branch.
        """
        for _rank, suffix in _LEVELS[index + 1:]:
            setattr(self, f"gbif_{suffix}", "")
            setattr(self, f"gbif_{suffix}_options", [_ANY])

    @rx.event(background=True)
    async def load_gbif_children(self, parent_key: int, index: int):
        """Populate the dropdown one level below ``index``.

        Background because the first lookup for a branch is a real HTTP call
        (~0.3–2.7 s measured); every later one is a memory hit in
        services/gbif_taxa.py. Running it inline would freeze the panel on the
        first open of each branch.
        """
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
        """Shared body of the seven per-rank setters."""
        index = self._level_index(suffix)
        if index < 0:
            return None
        chosen = "" if value == _ANY else value
        setattr(self, f"gbif_{suffix}", chosen)
        self._clear_below(index)
        # A free-text name pick and the cascade are two ways to say the same
        # thing, and honouring both at once would silently AND them. The
        # cascade is the one just used, so it wins.
        self._clear_name_search()
        self._refresh_layers()
        if not chosen:
            return None
        rank = _LEVELS[index][0]
        key = self._gbif_keys.get(f"{rank}:{chosen}")
        return None if key is None else GbifMixin.load_gbif_children(key, index)

    # Seven thin wrappers rather than one handler taking the rank: a Reflex
    # rx.select's on_change passes only the new value, so the rank has to be
    # bound at definition time.
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
        """Autocomplete against the GBIF backbone as the user types.

        Below three characters services/gbif_taxa.py returns nothing without
        asking the network, so the early keystrokes of every search are free.
        """
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
                # Discard a response the user has already typed past — the
                # requests are cached but not ordered, and a slow early one
                # landing last would replace the current suggestions with
                # stale ones.
                if self.gbif_name_query == value:
                    self.gbif_name_suggestions = [
                        {"key": str(r["key"]), "name": r["name"],
                         "rank": str(r["rank"] or "").title(),
                         "context": r["context"]}
                        for r in rows
                    ]

    def choose_gbif_suggestion(self, key: str, name: str):
        """Take one suggestion as the active taxon filter.

        Clears the cascade for the same reason the cascade clears this: two
        taxon filters at once would be ANDed, and "Aves AND Panthera onca"
        matches nothing while looking like it should match something.
        """
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
        """The year slider, as a two-handled range."""
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            return
        lo, hi = int(value[0]), int(value[1])
        # Both ends at their extremes means "no year filter at all" rather than
        # "1900 to this year", so a user who never touched the slider does not
        # silently exclude the handful of undated records.
        if lo <= gc.YEAR_MIN and hi >= self._year_now:
            self.gbif_year_from = 0
            self.gbif_year_to = 0
        else:
            self.gbif_year_from = lo
            self.gbif_year_to = hi
        self._refresh_layers()

    def set_gbif_uf(self, value: str):
        self.gbif_uf = "" if value == _ANY else value
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
        self.gbif_uf = ""
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
        """The deepest active taxonomic selection, or 0.

        A plain property, not an rx.var: it is read by ``gbif_filters`` on the
        server and never rendered, and an rx.var would be recomputed and
        shipped to the browser on every unrelated state change.
        """
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
        """The accordion, as the service's filter object."""
        uf_gid = ""
        if self.gbif_uf:
            uf_gid = next((gid for gid, uf, _name in gc.UF_GADM
                           if uf == self.gbif_uf), "")
        return gbif_service.Filters(
            taxon_key=self.gbif_taxon_key or None,
            basis_of_record=tuple(self.gbif_basis),
            year_from=self.gbif_year_from or None,
            year_to=self.gbif_year_to or None,
            gadm_gid=uf_gid,
        )

    @rx.var
    def gbif_opacity_pct(self) -> int:
        return int(round(self.gbif_opacity * 100))

    @rx.var
    def gbif_uf_options(self) -> list[str]:
        return [_ANY] + [uf for _gid, uf, _name in gc.UF_GADM]

    @rx.var
    def gbif_uf_value(self) -> str:
        return self.gbif_uf or _ANY

    @rx.var
    def gbif_has_filter(self) -> bool:
        return bool(self.gbif_taxon_key or self.gbif_basis or self.gbif_year_from
                    or self.gbif_year_to or self.gbif_uf)

    @rx.var
    def gbif_taxon_label(self) -> str:
        """What the badge shows for the active taxon — the deepest selection,
        or the picked name, or nothing."""
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
        """"300 de 22 400 nesta vista" — the layer's honesty line.

        Only ever shown when the count is genuinely truncated. At this zoom a
        viewport routinely holds tens of thousands of occurrences and the API
        returns at most 300 of them, so a layer that said nothing here would be
        presenting an arbitrary sample as if it were the data.
        """
        if not self.gbif_truncated or not self.gbif_in_view:
            return ""
        return f"{self.gbif_shown:,}/{self.gbif_in_view:,}".replace(",", " ")

    # ---------------------------------------------------------------------- #
    # Species in the buffers
    # ---------------------------------------------------------------------- #
    @rx.event(background=True)
    async def run_gbif_buffers(self):
        """Species recorded inside each buffer around the current study point.

        One faceted request per radius, fanned out concurrently in
        services/gbif_buffers.py (~2 s for all five, measured). Honours the same
        accordion filters as the map, so "birds only" narrows the species table
        exactly as it narrows the dots.
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
            logger.exception("GBIF buffer analysis failed")
            async with self:
                self.gbif_buffer_busy = False
                self.gbif_buffer_error = str(exc)
            return

        async with self:
            self.gbif_buffer_busy = False
            # The first non-empty error is reported rather than all five: they
            # share one upstream, so five failures are one failure.
            self.gbif_buffer_error = next((r.error for r in rows if r.error), "")
            self.gbif_buffer_rows = [
                GbifBufferRow(
                    radius_km=r.radius_km,
                    radius_label=f"{r.radius_km:g} km",
                    total=r.total,
                    total_label=f"{r.total:,}".replace(",", " "),
                    richness=r.richness,
                    # "1500+" rather than "1500" when GBIF's facet ceiling was
                    # reached: the true richness is unknown above it, and a
                    # bare number would state a floor as if it were a count.
                    richness_label=(f"{r.richness}+" if r.richness_truncated
                                    else str(r.richness)),
                    species=[
                        GbifSpeciesRow(name=n, count=c,
                                       count_label=f"{c:,}".replace(",", " "))
                        for n, c in r.species
                    ],
                    kingdoms=[GbifKingdomRow(name=n, count=c)
                              for n, c in r.kingdoms],
                    error=r.error,
                )
                for r in rows
            ]
