"""``/demonstracao`` — o passo a passo em rolagem de um ponto de verdade.

O artigo é ``reportagem/naturametrics.{html,js}`` sobre o kit compartilhado;
os números vêm de ``/_demonstracao/naturametrics.json``
(services/demonstracao.py). ``?ifn=`` ou ``?lat=&lon=`` trocam o ponto, com a
mesma sintaxe da página principal.
"""

from __future__ import annotations

import reflex as rx

from ..reportagem.kit import pagina


def demonstracao() -> rx.Component:
    return pagina("naturametrics")


def walkthrough() -> rx.Component:
    """``/walkthrough`` — the English walkthrough, on a point above Kelowna
    (naturametrics_ca.{en.html,js}, numbers from canada/services/demonstracao.py)."""
    return pagina("naturametrics_ca", lingua="en")


def walkthrough_brasil() -> rx.Component:
    """``/walkthrough/brazil`` — the Brazil article in English (naturametrics.en.html)."""
    return pagina("naturametrics", lingua="en")
