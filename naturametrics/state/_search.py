"""The location search box.

Ported from camposcope's SearchMixin, trimmed: naturametrics has no property
registry, so there is no CAR-code resolver and no candidate-chooser/
município-registration-browser UI — just navigation. Three resolvers a search
can land on (município, território, place name) tried in order after a
coordinate check, stopping at the first match; the box echoes how it read the
input before acting on it (services.geocode.resolve is the classifier, pure
and network-free).

Território covers terras indígenas (FUNAI) and unidades de conservação
(CNUC/ICMBio). Because a município and a territory can share a name, that one
resolver is offered alongside a município hit rather than only after it — see
``services/geocode.py``'s own docstring.

**Only a coordinate selects a study point** — a município, território or
place-name hit only frames the map (state._layers.fit_bounds, already
re-applied by the map whenever it changes). Finding a place and picking an
analysis point are different acts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import reflex as rx

from ..services import geocode, municipios, territorios
from ._proxy import state_class
from ..services.geocode import GeocodeError

logger = logging.getLogger(__name__)

#: How far to pad a single point with no bounding box of its own, so
#: fit_bounds does not zoom in on a zero-area box — same padding
#: services/ifn.py's extent() uses for the same reason.
_POINT_PAD_DEG = 0.05


class SearchMixin(rx.State, mixin=True):
    """What the user typed, how it was read, and what came back."""

    query: str = ""
    #: Human-readable "read as …", shown before anything happens.
    echo: str = ""
    echo_kind: str = ""
    search_error: str = ""
    searching_place: bool = False

    #: Município and território candidates (local, instant) and place
    #: candidates (geocoded).
    municipio_hits: List[Dict[str, Any]] = []
    territorio_hits: List[Dict[str, Any]] = []
    place_hits: List[Dict[str, Any]] = []

    @rx.var
    def has_search_results(self) -> bool:
        return bool(self.municipio_hits or self.territorio_hits
                    or self.place_hits)

    def _echo_text(self, resolution) -> str:
        """Rebuild the echo line in the current language.

        ``geocode.resolve`` is PT-only by design (a pure classifier, not a
        UI-facing service) and returns its own ``.echo`` pre-formatted in
        Portuguese. Only the noun ("coordenada"/"município"/"território"/
        "lugar") needs a language, so it is rebuilt here from ``kind`` +
        ``payload``.
        """
        kind, payload = resolution.kind, resolution.payload
        if kind == "coordenada":
            return f"{self.tr['echo_coordenada']} {payload.lat:.4f}, {payload.lon:.4f}"
        if kind == "municipio":
            first = payload[0]
            return f"{self.tr['echo_municipio']} {first['nome']}/{first['uf']}"
        if kind == "territorio":
            first = payload[0]
            return f"{self.tr['echo_territorio']} {first['nome']}"
        if kind == "lugar":
            return f"{self.tr['echo_lugar']} “{payload}”"
        return resolution.echo

    # --- typing ----------------------------------------------------------
    @rx.event
    def set_query(self, value: str) -> None:
        """Update the echo line as the user types — locally, with no requests.

        ``geocode.resolve`` classifies without performing anything, which is
        precisely what makes a live echo affordable: every keystroke costs a
        regex and a dict lookup, never a round trip.
        """
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
            # A coordinate that parsed but is unusable — a transposed pair, say.
            # Surface it while typing rather than on submit: the user is looking
            # at the field right now.
            self.echo = ""
            self.echo_kind = "erro"
            self.search_error = str(exc)

    # --- submitting -------------------------------------------------------
    @rx.event(background=True)
    async def submit_search(self):
        """Act on whatever the echo line already said this was."""
        async with self:
            raw = self.query.strip()
            self.search_error = ""
            self.municipio_hits = []
            self.territorio_hits = []
            self.place_hits = []
            if not raw:
                return

        try:
            resolution = geocode.resolve(raw)
        except ValueError as exc:
            async with self:
                self.search_error = str(exc)
            return

        kind = resolution.kind

        if kind == "coordenada":
            coord = resolution.payload
            # The one branch that selects a point, not just a place — same
            # entry point a map click uses (state/_point.py).
            return state_class(self).set_study_point(coord.lat, coord.lon)

        if kind == "municipio":
            async with self:
                self.municipio_hits = resolution.payload
                self.territorio_hits = list(resolution.territorios)
            # A single unambiguous hit goes straight there; several are
            # offered. A territory sharing the name makes it ambiguous too,
            # even when only one município matched — jumping to Jaú/SP while a
            # Parque Nacional do Jaú sits unmentioned in the list below would
            # be exactly the silent coin flip carrying both lists is meant to
            # avoid.
            if len(resolution.payload) == 1 and not resolution.territorios:
                return state_class(self).choose_municipio(
                    resolution.payload[0]["cod_municipio_ibge"]
                )
            return

        if kind == "territorio":
            async with self:
                self.territorio_hits = resolution.payload
            if len(resolution.payload) == 1:
                return state_class(self).choose_territorio(
                    resolution.payload[0]["tipo"], resolution.payload[0]["codigo"]
                )
            return

        # kind == "lugar" — the only branch that touches a third party.
        async with self:
            self.searching_place = True
        try:
            places = geocode.search_places(raw, limit=5)
        except GeocodeError as exc:
            async with self:
                self.searching_place = False
                self.search_error = str(exc)
            return

        async with self:
            self.searching_place = False
            if not places:
                self.search_error = self.tr["erro_lugar_nao_encontrado"].format(query=raw)
            self.place_hits = [
                {
                    "label": p.label,
                    "lat": p.lat,
                    "lon": p.lon,
                    "bounds": p.bounds or [],
                }
                for p in places
            ]

    # --- acting on a result ------------------------------------------------
    @rx.event(background=True)
    async def choose_municipio(self, cod_municipio_ibge: int):
        """Frame the map on a município. **Selects no point.**

        Framing a place and picking an analysis point are different acts —
        same reasoning as camposcope's search (doc/11 there, no equivalent
        doc here yet, but the same rule).
        """
        row = municipios.by_code(int(cod_municipio_ibge))
        if row is None:
            return

        async with self:
            self.municipio_hits = []
            self.query = f"{row['nome']}/{row['uf']}"
            self.echo = f"{self.tr['echo_municipio']} {row['nome']}/{row['uf']}"
            self.echo_kind = "municipio"

        # The boundary is the only part that costs a round trip, and only once a
        # município is actually chosen.
        box = municipios.bounds(int(cod_municipio_ibge))
        async with self:
            if box:
                self.fit_bounds = box

    @rx.event
    def choose_territorio(self, tipo: str, codigo: str) -> None:
        """Frame the map on a terra indígena or unidade de conservação, and
        draw the layer it belongs to. **Selects no study point.**

        Turning the layer on is the point of the gesture: framing a territory
        and then not drawing it would leave the user looking at an unmarked
        rectangle of map and wondering whether the search worked.

        No round trip, unlike ``choose_municipio``: the bbox is a committed
        column in ``data/territorios.csv``, computed from the full geometry,
        so framing is both instant and exact even though the drawn overlay is
        simplified to ~200 m.
        """
        key = f"{tipo}:{codigo}"
        row = territorios.by_key(key)
        if row is None:
            return

        self.territorio_hits = []
        self.municipio_hits = []
        self.place_hits = []
        if tipo == "indigena":
            self.show_terras_indigenas = True
        else:
            self.show_unidades_conservacao = True
        # Straight to the layer builder, not through the toggle handlers: they
        # take a checkbox's `checked` and each ends in its own
        # `_refresh_layers()`, so calling both would rebuild the spec list
        # twice for one gesture.
        self._refresh_layers()

        box = territorios.bounds(key)
        if box:
            self.fit_bounds = box

        self.query = row["nome"]
        self.echo = f"{self.tr['echo_territorio']} {row['nome']}"
        self.echo_kind = "territorio"

    @rx.event
    def choose_place(self, index: int) -> None:
        """Frame the map on a geocoded place. **Selects no point.**"""
        try:
            place = self.place_hits[int(index)]
        except (IndexError, ValueError, TypeError):
            return
        self.place_hits = []
        bounds = place.get("bounds")
        if not bounds:
            lat, lon = place["lat"], place["lon"]
            bounds = [[lat - _POINT_PAD_DEG, lon - _POINT_PAD_DEG],
                      [lat + _POINT_PAD_DEG, lon + _POINT_PAD_DEG]]
        self.fit_bounds = bounds
        self.query = place["label"]
        self.echo = f"{self.tr['echo_lugar']} — {self.tr['search_place_hint']}"
        self.echo_kind = "lugar"

    @rx.event
    def clear_search(self) -> None:
        self.query = ""
        self.echo = ""
        self.echo_kind = ""
        self.search_error = ""
        self.municipio_hits = []
        self.territorio_hits = []
        self.place_hits = []
