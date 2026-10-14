"""The Canada page's location search box — what was typed, how it was read,
and what came back.

The Brazil page's ``state/_search.py`` minus its município/território lists
(this page has neither table): a postal code or a place frames the map and
drops a pin; only an exact coordinate selects a study point, the search box's
equivalent of clicking the map there.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import reflex as rx

from ...services import address
from ...state._proxy import state_class
from ..services import geocode
from ..services.geocode import GeocodeError

logger = logging.getLogger(__name__)

#: Half-width of the box framed around a place that came back without one.
_POINT_PAD_DEG = 0.05


class CanadaSearchMixin(rx.State, mixin=True):
    """What the user typed, how it was read, and what came back."""

    query: str = ""
    #: Human-readable "read as …", shown before anything happens.
    echo: str = ""
    echo_kind: str = ""
    search_error: str = ""
    searching_place: bool = False
    place_hits: List[Dict[str, Any]] = []
    #: ``[lat, lon]`` of the chosen place, drawn as a pin on the map.
    search_pin: List[float] = []

    @rx.var(cache=True, deps=["buffer_overlays", "search_pin"], auto_deps=False)
    def map_overlays(self) -> Dict[str, Any]:
        """The study point's buffers plus the search pin. Explicit deps:
        ``buffer_overlays`` lives in another mixin and is read via
        ``getattr``, which the automatic dependency scan cannot see."""
        base = getattr(self, "buffer_overlays", None) or {
            "type": "FeatureCollection", "features": []}
        pin = self.search_pin
        if len(pin) != 2:
            return base
        return {
            **base,
            "type": "FeatureCollection",
            "features": list(base.get("features") or []) + [{
                "type": "Feature",
                "properties": {"role": "search_pin"},
                "geometry": {"type": "Point", "coordinates": [pin[1], pin[0]]},
            }],
        }

    @rx.var
    def place_attribution(self) -> str:
        """Credit exactly the sources the listed places came from."""
        return address.attributions(self.place_hits)

    def _msgs(self) -> Dict[str, str]:
        from ..translations import get_translations
        return get_translations(getattr(self, "language", "en"))

    def _echo_text(self, resolution) -> str:
        """``geocode.resolve`` is English-only by design; only the noun needs
        the page's language, so it is rebuilt here."""
        msgs = self._msgs()
        kind, payload = resolution.kind, resolution.payload
        if kind == "postal":
            return f"{msgs['echo_postal']} {payload}"
        if kind == "coordenada":
            return f"{msgs['echo_coordenada']} {payload.lat:.4f}, {payload.lon:.4f}"
        if kind == "lugar":
            return f"{msgs['echo_lugar']} “{payload}”"
        return resolution.echo

    # --- typing ----------------------------------------------------------
    @rx.event
    def set_query(self, value: str) -> None:
        """Update the echo line as the user types — locally, no requests."""
        self.query = value
        self.search_error = ""
        if not value.strip():
            self.echo = ""
            self.echo_kind = ""
            return
        try:
            resolution = geocode.resolve(value)
            self.echo = self._echo_text(resolution)
            self.echo_kind = resolution.kind
        except ValueError as exc:
            # A transposed or out-of-range coordinate: say so while the user
            # is still looking at the field.
            self.echo = ""
            self.echo_kind = "erro"
            self.search_error = str(exc)

    # --- submitting -------------------------------------------------------
    @rx.event(background=True)
    async def submit_search(self):
        async with self:
            raw = self.query.strip()
            self.search_error = ""
            self.place_hits = []
            if not raw:
                return
        try:
            resolution = geocode.resolve(raw)
        except ValueError as exc:
            async with self:
                self.search_error = str(exc)
            return

        if resolution.kind == "coordenada":
            coord = resolution.payload
            return state_class(self).set_study_point(coord.lat, coord.lon)

        if resolution.kind == "postal":
            async with self:
                self.searching_place = True
            try:
                places = geocode.search_postal(resolution.payload)
            except GeocodeError as exc:
                async with self:
                    self.searching_place = False
                    self.search_error = str(exc)
                return
            async with self:
                self.searching_place = False
                self.place_hits = [p.to_hit() for p in places]
                if not places:
                    self.search_error = self._msgs()[
                        "erro_postal_nao_encontrado"].format(code=resolution.payload)
            if places:
                return state_class(self).choose_place(0)
            return

        # kind == "lugar" — the only branch that guesses.
        async with self:
            self.searching_place = True
        try:
            places = geocode.search_places(raw, limit=6)
        except GeocodeError as exc:
            async with self:
                self.searching_place = False
                self.search_error = str(exc)
            return
        async with self:
            self.searching_place = False
            if not places:
                self.search_error = self._msgs()[
                    "erro_lugar_nao_encontrado"].format(query=raw)
            self.place_hits = [p.to_hit() for p in places]
        if len(places) == 1:
            return state_class(self).choose_place(0)

    # --- acting on a result ------------------------------------------------
    @rx.event
    def choose_place(self, index: int) -> None:
        """Frame the map on a geocoded place and pin it. **Selects no point.**

        Address- and postcode-level hits get a centre + zoom by precision
        (``fit_bounds`` is capped at z12 in leaflet_map.js); a town or region
        keeps its bounding box.
        """
        try:
            place = self.place_hits[int(index)]
        except (IndexError, ValueError, TypeError):
            return
        precision = place.get("precision", "lugar")
        lat, lon = place["lat"], place["lon"]
        if place.get("bounds") and precision not in address.POINT_PRECISIONS:
            self.fit_bounds = place["bounds"]
        elif precision in address.POINT_PRECISIONS:
            self.map_center = [lat, lon]
            self.map_zoom = address.ZOOM_BY_PRECISION.get(precision, 14)
        else:
            self.fit_bounds = [[lat - _POINT_PAD_DEG, lon - _POINT_PAD_DEG],
                               [lat + _POINT_PAD_DEG, lon + _POINT_PAD_DEG]]
        self.search_pin = [lat, lon]
        title = place.get("title") or place["label"]
        subtitle = place.get("subtitle") or ""
        self.query = f"{title}, {subtitle}" if subtitle else title
        msgs = self._msgs()
        self.echo = f"{msgs['echo_lugar']} — {msgs['search_place_hint']}"
        self.echo_kind = "lugar"

    @rx.event
    def clear_search(self) -> None:
        self.query = ""
        self.echo = ""
        self.echo_kind = ""
        self.search_error = ""
        self.place_hits = []
        self.search_pin = []
