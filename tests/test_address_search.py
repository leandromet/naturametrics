"""Address search (services/address.py, both pages' resolvers) and the
quick-start/how-to keys. The address module itself is shared verbatim with
camposcope, whose tests/test_address.py covers its parsing and labelling in
depth; this file covers what is wired differently here."""

from __future__ import annotations

import pytest

from naturametrics.services import address
from naturametrics.services import geocode as br
from naturametrics.canada.services import geocode as ca


def test_brazil_cep_is_its_own_kind():
    r = br.resolve("78890-000")
    assert r.kind == "cep" and r.payload == "78890000"


def test_brazil_street_address_reaches_the_geocoder():
    assert br.resolve("Avenida Paulista 1000, São Paulo").kind == "lugar"


def test_brazil_municipio_still_wins_over_address():
    assert br.resolve("Sorriso").kind == "municipio"


def test_canada_postal_coordinate_place():
    assert ca.resolve("v1y 2b3").kind == "postal"
    assert ca.resolve("49.88, -119.49").kind == "coordenada"
    assert ca.resolve("4700 Lakeshore Rd, Kelowna").kind == "lugar"


def test_canada_transposed_pair_is_named():
    with pytest.raises(ValueError, match="transposed"):
        ca.resolve("-119.49, 49.88")


def test_canada_resolve_performs_no_network_call(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("resolve() must not touch the network")
    monkeypatch.setattr(ca._geocoder, "_nominatim", boom)
    ca.resolve("Saskatoon")


_QS = ["qs_title", "qs_more", "qs_got_it", "qs_full_howto", "qs_close_aria",
       "help_show_quickstart", "search_place_hint",
       *[f"qs_step{n}_{p}" for n in range(1, 5) for p in ("lead", "body")],
       *[f"precision_{p}" for p in address.ZOOM_BY_PRECISION]]


@pytest.mark.parametrize("lang", ["pt", "en"])
def test_brazil_keys(lang):
    from naturametrics.translations import TRANSLATIONS
    keys = _QS + ["echo_cep", "erro_cep_nao_encontrado", "search_as_place"]
    assert not [k for k in keys if k not in TRANSLATIONS[lang]]


@pytest.mark.parametrize("lang", ["pt", "en"])
def test_canada_keys(lang):
    from naturametrics.canada.translations import TRANSLATIONS
    keys = _QS + ["search_title", "search_placeholder", "search_read_as",
                  "search_button", "search_button_busy", "search_clear_aria",
                  "search_places_heading", "search_places_note", "echo_postal",
                  "echo_coordenada", "echo_lugar", "erro_postal_nao_encontrado",
                  "erro_lugar_nao_encontrado"]
    assert not [k for k in keys if k not in TRANSLATIONS[lang]]


def test_search_pin_reaches_the_map_overlays():
    """The pin is drawn through map_overlays — whose dependency on it must be
    declared, or setting it would never reach the browser."""
    from naturametrics.canada.state import CanadaState
    from naturametrics.state import AppState
    for S in (AppState, CanadaState):
        deps = {name for _, name in S._var_dependencies.get("search_pin", set())}
        assert "map_overlays" in deps
        deps = {name for _, name in S._var_dependencies.get("buffer_overlays", set())}
        assert "map_overlays" in deps
