"""The committed FUNAI/CNUC territory catalogue and its two map overlays."""

from __future__ import annotations

import gzip
import json

import pytest

from naturametrics.config.datasets import TERRITORIOS
from naturametrics.services import territorios


def test_catalogue_is_complete():
    assert territorios.count("indigena") == 657
    assert territorios.count("conservacao") == 3247


def test_search_is_accent_insensitive():
    names = [r["nome"] for r in territorios.search("kayapo")]
    assert any("Kayapó" in n for n in names)


def test_search_prefers_prefix_matches():
    assert territorios.search("yanomami")[0]["nome"] == "Yanomami"


def test_search_accepts_a_uf_suffix():
    rows = territorios.search("kayapó/PA")
    assert rows
    assert all("PA" in r["uf"].split(", ") for r in rows)


def test_search_can_be_scoped_to_one_type():
    rows = territorios.search("reserva", tipo="conservacao")
    assert rows
    assert all(r["tipo"] == "conservacao" for r in rows)


def test_search_ignores_one_character_queries():
    """A substring pass over 3 900 names on a single letter is the whole list,
    not a search."""
    assert territorios.search("a") == []
    assert territorios.search("") == []


def test_bounds_are_a_south_west_north_east_box():
    key = f"conservacao:{territorios.search('Tijuca', tipo='conservacao')[0]['codigo']}"
    (south, west), (north, east) = territorios.bounds(key)
    assert south < north and west < east
    # Parque Nacional da Tijuca, in Rio de Janeiro.
    assert -23.1 < south < -22.8
    assert -43.4 < west < -43.1


def test_bounds_of_an_unknown_key_is_none():
    assert territorios.bounds("indigena:not-a-code") is None
    assert territorios.by_key("conservacao:not-a-code") is None


@pytest.mark.parametrize("tipo", territorios.TIPOS)
def test_overlay_is_valid_gzipped_geojson(tipo):
    payload = territorios.geojson_gzipped(tipo)
    data = json.loads(gzip.decompress(payload))
    assert data["type"] == "FeatureCollection"
    assert data["features"]
    for feature in data["features"]:
        assert feature["geometry"]["type"] in ("Polygon", "MultiPolygon")


@pytest.mark.parametrize("tipo", territorios.TIPOS)
def test_every_overlay_feature_carries_what_the_spec_reads(tipo):
    """The label and every tooltip row name a property; a spec pointing at a
    field the data does not have renders a blank row, silently."""
    spec = territorios.vector_spec(tipo)
    data = json.loads(gzip.decompress(territorios.geojson_gzipped(tipo)))
    wanted = {spec["label_property"]} | {t["property"] for t in spec["tooltip"]}
    for feature in data["features"][:50]:
        assert wanted <= set(feature["properties"])


@pytest.mark.parametrize("tipo", territorios.TIPOS)
def test_spec_colours_the_whole_layer_one_hue(tipo):
    """No `color_property`: styleFor falls through to `default_color`, which
    is what makes gold mean "terra indígena" and dark purple "unidade de
    conservação" without a legend lookup."""
    spec = territorios.vector_spec(tipo)
    assert "color_property" not in spec
    assert spec["default_color"] == TERRITORIOS[tipo]["color"]


def test_hiding_labels_changes_the_layer_id():
    """leaflet_map.js builds label markers once, at build time — a same-id
    'cheap property update' would silently leave the old markers in place."""
    with_labels = territorios.vector_spec("indigena", show_labels=True)
    without = territorios.vector_spec("indigena", show_labels=False)
    assert with_labels["id"] != without["id"]
    assert without["label_property"] is None


# --------------------------------------------------------------------------- #
# The search resolver (services/geocode.py)
# --------------------------------------------------------------------------- #
def test_precedence_territorio_before_place():
    """"Yanomami" is a terra indígena, so it must never reach the geocoder."""
    from naturametrics.services import geocode

    r = geocode.resolve("Yanomami")
    assert r.kind == "territorio"
    assert r.payload[0]["nome"] == "Yanomami"


def test_municipio_carries_its_territory_namesakes():
    """A município and a territory can share a name, and picking one silently
    would be a coin flip. "Jaú" is a município in São Paulo AND a national
    park in Amazonas: the echo still reads "município", and the park is
    offered rather than dropped."""
    from naturametrics.services import geocode

    r = geocode.resolve("jau")
    assert r.kind == "municipio"
    assert any("JAÚ" in t["nome"].upper() for t in r.territorios)


def test_only_a_municipio_hit_carries_territories():
    """Every other kind is unambiguous, or reached the geocoder precisely
    because nothing local matched."""
    from naturametrics.services import geocode

    assert geocode.resolve("-12.4979, -55.4977").territorios == []
    assert geocode.resolve("Fazenda Santa Luzia do Norte").territorios == []
