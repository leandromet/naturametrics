"""UI text in more than one language.

Portuguese is canonical: ``TRANSLATIONS_PT`` is the reference key set, and every
other language falls back to it for any key it does not (yet) define — an
incomplete language never shows a blank or a raw key, just Portuguese.

Most of the app's text still lives inline in components/state as hardcoded
Portuguese; this module only covers the keys that have been wired to
``AppState.tr``. See doc/ for what remains (help/citation dialog content,
service-layer parse/estimate messages).
"""

from __future__ import annotations

from .en import TRANSLATIONS_EN
from .pt import TRANSLATIONS_PT

TRANSLATIONS: dict[str, dict[str, str]] = {
    "pt": TRANSLATIONS_PT,
    "en": TRANSLATIONS_EN,
}


def get_translations(lang: str) -> dict[str, str]:
    """All keys for ``lang``, with Portuguese filling in anything missing."""
    overrides = TRANSLATIONS.get(lang)
    if not overrides or lang == "pt":
        return TRANSLATIONS_PT
    return {**TRANSLATIONS_PT, **overrides}


def t(key: str, lang: str) -> str:
    return get_translations(lang).get(key, key)


def missing_keys() -> dict[str, set[str]]:
    """Keys each non-reference language is missing or has extra, vs. Portuguese."""
    ref = set(TRANSLATIONS_PT)
    out = {}
    for lang, table in TRANSLATIONS.items():
        if lang == "pt":
            continue
        diff = ref ^ set(table)
        if diff:
            out[lang] = diff
    return out
