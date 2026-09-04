"""UI chrome state for the Canada page: language, panel visibility."""

from __future__ import annotations

import reflex as rx

from ...config.settings import SUPPORTED_LANGUAGES
from ..config.settings import DEFAULT_LANGUAGE
from ..translations import get_translations


class CanadaUIMixin(rx.State, mixin=True):
    """Presentation state with no analytical meaning."""

    #: Defaults to English (``canada/config/settings.DEFAULT_LANGUAGE``) rather
    #: than the app-wide Portuguese. An explicit choice still wins: the header
    #: link between the two pages carries ``?lang=``, and :meth:`on_load` honours
    #: it, so a user reading the Brazil page in English does not get bounced back
    #: to Portuguese on return — and vice versa.
    language: str = DEFAULT_LANGUAGE

    #: Mobile overlay drawer only; the desktop sidebar is always visible.
    sidebar_open: bool = False

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

    def adopt_lang_param(self):
        """Honour ``?lang=`` on page load — the receiving end of the header link.

        Absent or unrecognised, the page keeps its own English default rather
        than the app-wide Portuguese one.
        """
        requested = (self.router.page.params or {}).get("lang")
        if requested in SUPPORTED_LANGUAGES:
            self.language = requested

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

    def set_cite_open(self, value: bool):
        self.cite_open = value

    @rx.var
    def tr(self) -> dict[str, str]:
        return get_translations(self.language)

    @rx.var
    def brazil_href(self) -> str:
        """Link back to the Brazil page, carrying the current language."""
        return f"/?lang={self.language}"
