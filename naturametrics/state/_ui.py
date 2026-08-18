"""UI chrome state: language, panel visibility."""

from __future__ import annotations

import reflex as rx

from ..config import settings as st


class UIMixin(rx.State, mixin=True):
    """Presentation state with no analytical meaning."""

    language: str = st.DEFAULT_LANGUAGE
    sidebar_open: bool = True

    def set_language(self, lang: str):
        if lang in st.SUPPORTED_LANGUAGES:
            self.language = lang

    def toggle_sidebar(self):
        self.sidebar_open = not self.sidebar_open
