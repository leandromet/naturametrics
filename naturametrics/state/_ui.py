"""UI chrome state: language, panel visibility."""

from __future__ import annotations

import reflex as rx

from ..config import settings as st
from ..translations import get_translations


class UIMixin(rx.State, mixin=True):
    """Presentation state with no analytical meaning."""

    language: str = st.DEFAULT_LANGUAGE
    #: Controls the MOBILE overlay drawer only — the desktop sidebar is
    #: always visible. Starts closed so the map is the first thing seen.
    sidebar_open: bool = False

    def set_language(self, lang: str | list[str]):
        raw = lang[0] if isinstance(lang, (list, tuple)) and lang else lang
        if raw in st.SUPPORTED_LANGUAGES:
            self.language = raw

    def adopt_lang_param(self):
        """Honour ``?lang=`` on page load.

        The Canada page is a separate state root, so the language cannot be
        read across from it — the link between the two carries it in the URL and
        this is the receiving end. Absent or unrecognised, the page keeps its own
        default (Portuguese here, English there).
        """
        requested = (self.router.page.params or {}).get("lang")
        if requested in st.SUPPORTED_LANGUAGES:
            self.language = requested

    def toggle_sidebar(self):
        self.sidebar_open = not self.sidebar_open

    @rx.var
    def tr(self) -> dict[str, str]:
        return get_translations(self.language)

    @rx.var
    def canada_href(self) -> str:
        """Link across to the Canada page, carrying the current language.

        The two pages have separate state roots, so the language cannot simply
        be read across — it travels in the URL. Without this, a user reading
        this page in English would land on ``/canada`` in whatever that page's
        default happens to be.
        """
        return f"/canada?lang={self.language}"
