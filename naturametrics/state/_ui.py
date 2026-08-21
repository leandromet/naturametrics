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

    def toggle_sidebar(self):
        self.sidebar_open = not self.sidebar_open

    @rx.var
    def tr(self) -> dict[str, str]:
        return get_translations(self.language)
