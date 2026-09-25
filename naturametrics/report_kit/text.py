"""Locale formatting and the kit's own fixed strings, in pt / en / es / fr.

Apps format every number in their explanatory sentences through these, so a
Portuguese report reads "1.234,5 ha" and an English one "1,234.5 ha" without
each app re-implementing it. Strings an *app* owns (section titles, its
sentences) stay in the app; only what the kit itself prints lives here.
"""

from __future__ import annotations

import html as _html
import re as _re
from datetime import date, datetime
from typing import Optional, Union

LANGS = ("pt", "en", "es", "fr")

# (thousands separator, decimal separator, space before %)
_NUM = {
    "pt": (".", ",", " "),
    "es": (".", ",", " "),
    "fr": (" ", ",", " "),   # narrow no-break space
    "en": (",", ".", ""),
}


def _lang(lang: Optional[str]) -> str:
    return lang if lang in _NUM else "en"


def fmt_num(value: Union[int, float, None], decimals: int = 1,
            lang: str = "pt") -> str:
    """``1234.5`` → pt/es ``1.234,5``, fr ``1 234,5``, en ``1,234.5``.
    ``None``/NaN → an em dash, never "nan"."""
    if value is None or value != value:   # NaN check without math import
        return "—"
    thou, dec, _ = _NUM[_lang(lang)]
    text = f"{float(value):,.{decimals}f}"          # en form first
    return text.replace(",", "\x00").replace(".", dec).replace("\x00", thou)


def fmt_int(value, lang: str = "pt") -> str:
    return fmt_num(value, 0, lang)


def fmt_ha(value, decimals: int = 1, lang: str = "pt") -> str:
    return f"{fmt_num(value, decimals, lang)} ha"


def fmt_pct(value, decimals: int = 1, lang: str = "pt") -> str:
    if value is None or value != value:
        return "—"
    _, _, sp = _NUM[_lang(lang)]
    return f"{fmt_num(value, decimals, lang)}{sp}%"


def fmt_signed(value, decimals: int = 1, lang: str = "pt") -> str:
    """With an explicit sign and a true minus (−), for differences."""
    if value is None or value != value:
        return "—"
    body = fmt_num(abs(value), decimals, lang)
    return ("+" if value > 0 else "−" if value < 0 else "") + body


def fmt_date(value: Union[str, date, datetime, None], lang: str = "pt") -> str:
    """ISO in, locale out: pt/es/fr ``22/07/2008``, en ``2008-07-22``."""
    if value in (None, ""):
        return "—"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value[:19])
        except ValueError:
            return value
    if _lang(lang) == "en":
        return value.strftime("%Y-%m-%d")
    return value.strftime("%d/%m/%Y")


def fmt_cell(value, decimals: Optional[int] = None, lang: str = "pt") -> str:
    """A table cell: numbers in the locale (floats 1 decimal unless told),
    None/NaN as an em dash, anything else as its string."""
    if value is None or (isinstance(value, float) and value != value):
        return "—"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return fmt_num(value, 0 if decimals is None else decimals, lang)
    if isinstance(value, float):
        return fmt_num(value, 1 if decimals is None else decimals, lang)
    try:  # numpy scalars
        import numbers
        if isinstance(value, numbers.Integral):
            return fmt_num(int(value), 0 if decimals is None else decimals, lang)
        if isinstance(value, numbers.Real):
            return fmt_cell(float(value), decimals, lang)
    except ImportError:  # pragma: no cover
        pass
    return str(value)


def fmt_datetime_utc(value: datetime, lang: str = "pt") -> str:
    base = fmt_date(value, lang)
    return f"{base} {value.strftime('%H:%M')} UTC"


# --------------------------------------------------------------------------- #
# Kit strings
# --------------------------------------------------------------------------- #

STRINGS = {
    "figure": {"pt": "Figura", "en": "Figure", "es": "Figura", "fr": "Figure"},
    "table": {"pt": "Tabela", "en": "Table", "es": "Tabla", "fr": "Tableau"},
    "page_of": {"pt": "página {n} de {total}", "en": "page {n} of {total}",
                "es": "página {n} de {total}", "fr": "page {n} sur {total}"},
    "generated": {"pt": "gerado em", "en": "generated", "es": "generado el",
                  "fr": "généré le"},
    "version": {"pt": "versão", "en": "version", "es": "versión", "fr": "version"},
    "figure_unavailable": {
        "pt": "Figura indisponível", "en": "Figure unavailable",
        "es": "Figura no disponible", "fr": "Figure indisponible"},
    "rows_more": {
        "pt": "… mais {n} linhas não mostradas (ver apêndice ou planilha)",
        "en": "… {n} more rows not shown (see the appendix or the spreadsheet)",
        "es": "… {n} filas más no mostradas (ver apéndice u hoja de cálculo)",
        "fr": "… {n} lignes supplémentaires non affichées (voir l'annexe ou le tableur)"},
    "status_included": {"pt": "incluído", "en": "included", "es": "incluido",
                        "fr": "inclus"},
    "status_not_run": {"pt": "não calculado", "en": "not run",
                       "es": "no calculado", "fr": "non calculé"},
    "status_unavailable": {"pt": "indisponível", "en": "unavailable",
                           "es": "no disponible", "fr": "indisponible"},
    "status_excluded": {"pt": "excluído", "en": "excluded", "es": "excluido",
                        "fr": "exclu"},
    "prov_name": {"pt": "Análise", "en": "Analysis", "es": "Análisis", "fr": "Analyse"},
    "prov_dataset": {"pt": "Conjunto de dados", "en": "Dataset",
                     "es": "Conjunto de datos", "fr": "Jeu de données"},
    "prov_bands": {"pt": "Bandas", "en": "Bands", "es": "Bandas", "fr": "Bandes"},
    "prov_scale": {"pt": "Escala", "en": "Scale", "es": "Escala", "fr": "Échelle"},
    "prov_reducer": {"pt": "Redutor", "en": "Reducer", "es": "Reductor",
                     "fr": "Réducteur"},
    "prov_computed": {"pt": "Calculado em", "en": "Computed", "es": "Calculado el",
                      "fr": "Calculé le"},
    "prov_degraded": {"pt": "resolução reduzida", "en": "degraded",
                      "es": "resolución reducida", "fr": "résolution réduite"},
    "sources": {"pt": "Fontes de dados", "en": "Data sources",
                "es": "Fuentes de datos", "fr": "Sources de données"},
    "attributions": {"pt": "Atribuições", "en": "Attributions",
                     "es": "Atribuciones", "fr": "Attributions"},
    "how_to_cite": {"pt": "Como citar", "en": "How to cite", "es": "Cómo citar",
                    "fr": "Comment citer"},
    "north": {"pt": "N", "en": "N", "es": "N", "fr": "N"},
}


def t(key: str, lang: str = "pt", **kw) -> str:
    """A kit string in ``lang`` (fallback en). Formatting placeholders are
    filled here, in Python — never on a Reflex Var."""
    table = STRINGS[key]
    text = table.get(lang) or table["en"]
    return text.format(**kw) if kw else text


# --------------------------------------------------------------------------- #
# Inline markup
# --------------------------------------------------------------------------- #

_BOLD = _re.compile(r"\*\*(.+?)\*\*", _re.S)
_ITAL = _re.compile(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", _re.S)


def inline_markup(text: str) -> str:
    """Escape ``text`` for (reportlab or HTML) markup, then turn ``**x**``
    into ``<b>x</b>`` and ``*x*`` into ``<i>x</i>``. Nothing else survives
    as markup — an app's data can never inject a tag."""
    out = _html.escape(str(text), quote=False)
    out = _BOLD.sub(r"<b>\1</b>", out)
    return _ITAL.sub(r"<i>\1</i>", out)
