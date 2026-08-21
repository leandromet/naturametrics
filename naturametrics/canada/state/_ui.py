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

    @rx.var
    def tr(self) -> dict[str, str]:
        return get_translations(self.language)

    @rx.var
    def brazil_href(self) -> str:
        """Link back to the Brazil page, carrying the current language."""
        return f"/?lang={self.language}"
