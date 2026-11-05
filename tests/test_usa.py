"""The USA page (lower 48): offline checks on its config, geo bounds, ZIP parsing and
translations, plus one live Earth Engine check (``-m ee``) that the NLCD history agrees
with the buffer's true area.
"""

import re

import pytest

from naturametrics.usa.config import nlcd
from naturametrics.usa.services import geocode
from naturametrics.usa.services.geo import Point, in_usa_box, looks_swapped
from naturametrics.usa.translations import TRANSLATIONS_EN, TRANSLATIONS_PT


def test_nlcd_years_and_bands():
    assert nlcd.NLCD_YEARS[0] == 1985 and nlcd.NLCD_YEARS[-1] == 2025
    assert len(nlcd.all_bands()) == len(set(nlcd.all_bands())) == 41


def test_every_class_has_both_labels_and_a_colour():
    assert set(nlcd.NLCD_LABELS_EN) == set(nlcd.NLCD_LABELS_PT) == set(nlcd.NLCD_COLOR_MAP)
    assert len(nlcd.NLCD_PALETTE) == nlcd.NLCD_VIS["max"] + 1


def test_groups_do_not_overlap_and_stay_inside_the_legend():
    groups = [nlcd.FOREST, nlcd.WETLAND, nlcd.GRASS_SHRUB, nlcd.WATER, nlcd.BARREN,
              nlcd.URBAN, nlcd.CROPLAND]
    seen: set[int] = set()
    for g in groups:
        assert not (seen & g)
        seen |= g
    assert seen <= set(nlcd.NLCD_LABELS_EN)


def test_box_and_swap_detection():
    assert in_usa_box(Point(lat=39.5, lon=-98.5))
    assert not in_usa_box(Point(lat=-15.8, lon=-47.9))      # Brasília
    assert in_usa_box(Point(lat=64.8, lon=-147.7))          # Fairbanks: Alaska is in
    assert in_usa_box(Point(lat=21.3, lon=-157.9))          # Honolulu: Hawaii is in
    assert not in_usa_box(Point(lat=18.4, lon=-66.1))       # San Juan: Puerto Rico is out
    assert not in_usa_box(Point(lat=52.5, lon=175.0))       # western Aleutians: out


def test_zip_parsing():
    assert geocode.parse_zip("66801") == "66801"
    assert geocode.parse_zip(" 66801-1234 ") == "66801"
    assert geocode.parse_zip("6680") is None
    assert geocode.resolve("66801").kind == "postal"
    assert geocode.resolve("39.5, -98.5").kind == "coordenada"
    assert geocode.resolve("Emporia KS").kind == "lugar"


def test_translations_have_the_same_placeholders_in_both_languages():
    pat = re.compile(r"\{[a-z_0-9.:]+\}")
    for key, pt in TRANSLATIONS_PT.items():
        en = TRANSLATIONS_EN.get(key)
        assert en is not None, f"{key} is in PT but not in EN"
        assert sorted(pat.findall(en)) == sorted(pat.findall(pt)), key


def test_regions_and_year_snapping():
    from naturametrics.usa.services.geo import region_of
    assert region_of(Point(lat=39.5, lon=-98.5)) == "conus"
    assert region_of(Point(lat=61.2, lon=-149.9)) == "ak"
    assert region_of(Point(lat=21.3, lon=-157.9)) == "hi"
    assert nlcd.years_for("ak") == [2001, 2011, 2016] and nlcd.years_for("hi") == []
    assert nlcd.nearest_year("ak", 2025) == 2016 and nlcd.nearest_year("conus", 1990) == 1990


def test_disturbance_config_is_consistent():
    from naturametrics.usa.config import disturbance as d
    assert set(d.CHANGE_LABELS_EN) == set(d.CHANGE_LABELS_PT) == set(d.CHANGE_COLORS)
    assert set(d.TREE_DISTURBANCE) <= set(d.LOSS_CLASSES)
    assert d.AGE_ORDER[-1] == d.AGE_CENSORED and set(d.AGE_ORDER) == set(d.AGE_COLORS)
    assert set(d.SEVERITY_LABELS_EN) == set(d.SEVERITY_LABELS_PT) == set(d.SEVERITY_COLORS)


def test_no_leftover_canadian_vocabulary_in_the_translations():
    bad = re.compile(r"Canad|AAFC|NTEMS|ACI\b|Kelowna|Prairie|58°N", re.I)
    for table in (TRANSLATIONS_EN, TRANSLATIONS_PT):
        for key, text in table.items():
            if key in {"go_to_canada"} or "Brazil or Canada page" in text \
                    or "Brasil ou do Canadá" in text:
                continue
            assert not bad.search(text), (key, text)


@pytest.mark.ee
def test_history_areas_match_the_disc_area():
    from naturametrics.usa.services.nlcd_history import land_cover_history

    df, _ = land_cover_history(Point(lat=39.5, lon=-98.5), radii_km=(1.0,), years=[2025])
    expected_ha = 3.14159 * 1000 ** 2 / 10_000
    assert df["area_ha"].sum() == pytest.approx(expected_ha, rel=0.03)
