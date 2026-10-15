"""The platform switcher shared by the three UmaTerra apps (components/suite_links.py)."""

from __future__ import annotations

import naturametrics.components.suite_links as sl


def test_every_platform_is_described_in_every_language():
    for platform in (sl.PORTAL, *sl.PLATFORMS):
        assert sl.NAMES[platform] and sl.ICONS[platform]
        assert set(sl.DESCRIPTIONS[platform]) == {"en", "pt", "es", "fr"}, platform
        assert all(len(t) > 40 for t in sl.DESCRIPTIONS[platform].values())
    assert set(sl.HERE) == set(sl.TITLE) == {"en", "pt", "es", "fr"}


def test_links_keep_the_region_and_the_language():
    assert sl.href("camposcope", "brazil", "pt") == "https://camposcope.umaterra.com.br/?lang=pt"
    assert sl.href("naturametrics", "canada", "en") == "https://naturametrics.umaterra.com.br/canada?lang=en"
    assert sl.href("yvynation", "canada", "fr") == "https://yvynation.umaterra.com.br/canada?lang=fr"
    # muda-clima has a single page (its console) and no Canada version.
    assert sl.href("clima", "canada", "en") == "https://clima.umaterra.com.br/app/?lang=en"


def test_base_urls_can_be_pointed_at_local_servers(monkeypatch):
    monkeypatch.setenv("UMATERRA_URL_YVYNATION", "http://localhost:3000/")
    assert sl.base_url("yvynation") == "http://localhost:3000"
    assert sl.href("yvynation", "brazil", "en") == "http://localhost:3000/?lang=en"


def test_the_switcher_renders_chips_and_a_menu():
    import reflex as rx
    comp = sl.suite_links("naturametrics", region="brazil", language="en")
    html = str(comp)
    for name in sl.NAMES.values():
        assert name in html
    assert "layout-grid" in html or "LayoutGrid" in html      # the compact menu button
    assert "aria_current" in html or "aria-current" in html   # this app is "here"


def test_compact_mode_is_the_menu_only():
    compact = str(sl.suite_links("naturametrics", region="canada", language="en", compact=True))
    assert "layout-grid" in compact or "LayoutGrid" in compact
    assert "aria_current" not in compact and "aria-current" not in compact


def test_portal_link_lands_on_the_matching_language_page():
    js = str(sl.href(sl.PORTAL, "brazil", "es"))
    for path in ('umaterra.com.br/"', "umaterra.com.br/es/", "umaterra.com.br/fr/", "umaterra.com.br/en/"):
        assert path.rstrip('"') in js, path
