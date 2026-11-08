"""UI chrome state for the USA page: language, panel visibility."""

from __future__ import annotations

import reflex as rx

from ...components.lang_pref import detect_language_event, store_script

from ...config.settings import SUPPORTED_LANGUAGES
from ..config.settings import DEFAULT_LANGUAGE
from ..translations import get_translations


class WorldUIMixin(rx.State, mixin=True):
    """Presentation state with no analytical meaning."""

    #: Defaults to English (``usa/config/settings.DEFAULT_LANGUAGE``) rather
    #: than the app-wide Portuguese. An explicit choice still wins: the header
    #: link between the two pages carries ``?lang=``, and :meth:`on_load` honours
    #: it, so a user reading the Brazil page in English does not get bounced back
    #: to Portuguese on return — and vice versa.
    language: str = DEFAULT_LANGUAGE

    #: Mobile overlay drawer only; the desktop sidebar is always visible.
    sidebar_open: bool = False

    #: Which sidebar groups are open (controlled, like the Brazil page's ``open_groups``).
    open_groups: list[str] = ["study_area"]

    def set_open_groups(self, value: str | list[str]):
        # typed str | list[str] to pass Reflex's accordion event-spec check; always a list here
        self.open_groups = [value] if isinstance(value, str) else list(value)

    #: The on-map legend collapsed to just its header — see the Brazil page's
    #: own ``state/_ui.py`` for why this default is decided in the browser.
    legend_open: bool = True
    _viewport_adopted: bool = False

    #: The header's two info dialogs, fully controlled for the same reason as
    #: the Brazil page's equivalents (state/_ui.py::UIMixin) — Dialog.Close's
    #: Radix "asChild" prop-cloning never reaches a button Reflex has extracted
    #: into its own standalone helper component, so the close button renders
    #: but does nothing without an explicit on_click driving this state instead.
    help_open: bool = False
    cite_open: bool = False

    #: The desktop results-drawer's height — see the Brazil page's own
    #: ``state/_ui.py::UIMixin`` for the full rationale (a desktop
    #: counterpart to the mobile sheet's tap-to-toggle height, which desktop
    #: never had).
    results_panel_size: str = "half"

    def cycle_results_panel_size(self):
        order = ["compact", "half", "expanded"]
        idx = order.index(self.results_panel_size) if self.results_panel_size in order else 1
        self.results_panel_size = order[(idx + 1) % len(order)]

    @rx.var
    def results_panel_height(self) -> str:
        return {"compact": "22vh", "half": "42vh", "expanded": "68vh"}.get(
            self.results_panel_size, "42vh")

    def set_language(self, lang: str | list[str]):
        raw = lang[0] if isinstance(lang, (list, tuple)) and lang else lang
        if raw in SUPPORTED_LANGUAGES:
            self.language = raw
            return rx.call_script(store_script(raw))

    def detect_language(self):
        """On load: the language this page opens in (see components/lang_pref.py)."""
        return detect_language_event(type(self), SUPPORTED_LANGUAGES)

    def apply_detected_language(self, lang: str):
        if lang in SUPPORTED_LANGUAGES:
            self.language = lang

    def adopt_lang_param(self):
        """Honour ``?lang=`` on page load — the receiving end of the header link.

        Absent or unrecognised, the page keeps its own English default rather
        than the app-wide Portuguese one.
        """
        requested = (self.router.page.params or {}).get("lang")
        if requested in SUPPORTED_LANGUAGES:
            self.language = requested

    def adopt_url_params(self):
        """``on_load``: ``?lang=``, then ``?lat=&lon=`` as a map click (the other pages send an out-of-country
        click here, so a point on any country opens its analysis)."""
        self.adopt_lang_param()
        params = self.router.page.params or {}
        try:
            lat, lon = float(params["lat"]), float(params["lon"])
        except (KeyError, TypeError, ValueError):
            return None
        events = self.set_study_point(lat, lon)
        if not self.has_point:
            return events
        frame = rx.call_script(
            "(function () { var n = 0; var t = setInterval(function () {"
            "  var el = document.getElementById('nm-world-map'); var map = el && el._nmMap;"
            f"  if (map) {{ clearInterval(t); map.setView([{lat}, {lon}], 10); }}"
            "  else if (++n > 100) clearInterval(t);"
            "}, 100); })()"
        )
        return [*(events if isinstance(events, list) else [events]), frame]

    def toggle_sidebar(self):
        self.sidebar_open = not self.sidebar_open

    def toggle_legend(self):
        self.legend_open = not self.legend_open

    def adopt_viewport(self, narrow: bool):
        """Collapse the on-map legend on a phone, once per session — the
        Brazil page's ``state/_ui.py::adopt_viewport``, ported. Only ever
        collapses, so it cannot fight a user who opened it themselves."""
        if self._viewport_adopted:
            return
        self._viewport_adopted = True
        if narrow:
            self.legend_open = False

    def set_help_open(self, value: bool):
        self.help_open = value

    #: "1" once this browser dismissed the quick-start card — browser storage,
    #: a per-viewer convenience (see the Brazil page's ``state/_ui.py``). Its
    #: own key: the USA card says different things.
    quickstart_seen: str = rx.SessionStorage("", name="naturametrics_quickstart_us_v1")

    @rx.var
    def show_quickstart(self) -> bool:
        return self.quickstart_seen != "1"

    def dismiss_quickstart(self):
        self.quickstart_seen = "1"

    def open_full_howto(self):
        self.quickstart_seen = "1"
        self.help_open = True

    def reset_quickstart(self):
        self.quickstart_seen = ""
        self.help_open = False

    def set_cite_open(self, value: bool):
        self.cite_open = value

    @rx.var
    def tr(self) -> dict[str, str]:
        return get_translations(self.language)

    @rx.var
    def brazil_href(self) -> str:
        """Link back to the Brazil page, carrying the current language."""
        return f"/?lang={self.language}"

    @rx.var
    def canada_href(self) -> str:
        """Link to the Canada page, carrying the current language."""
        return f"/canada?lang={self.language}"

    @rx.var
    def usa_href(self) -> str:
        """Link to the USA page (lower 48), carrying the current language."""
        return f"/usa?lang={self.language}"
