"""Demonstrações em rolagem — a página Reflex em volta de um artigo.

Arquivo compartilhado por hash entre Naturametrics (canônico), Camposcope e
Yvynation: edite em ``naturametrics/reportagem/kit.py`` e rode
``scripts/sync_shared_files.py``. muda-clima não é Reflex e usa só
``kit.css``/``kit.js``.

Um artigo é um par de arquivos ao lado deste: ``<nome>.html`` (o corpo, com
``.rp-passo`` e ``.rp-camada``) e ``<nome>.js`` (os tratadores de cada passo,
que chamam ``Reportagem.iniciar``). Os números vêm de uma rota JSON do backend
do próprio aplicativo, servida pelo Starlette como os GeoJSON de biomas — por
HTTP, não pelo WebSocket, porque são iguais para todo visitante.

O corpo entra como HTML cru (``rx.html``) e o script por
``on_mount=rx.call_script``: o artigo é texto e um motor em JS, e reescrevê-lo
em componentes Reflex não acrescentaria nada além de um estado que ninguém lê.
**Não** ``rx.script`` — um ``<script>`` filho é inserido pelo React via
innerHTML (o navegador não executa) e o Helmet também não o roda; o mesmo
defeito já documentado em ``camposcope/pages/index.py`` (``_SHEET_SCRIPT``).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import reflex as rx
from reflex.config import get_config

_AQUI = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def ler(nome: str) -> str:
    """Um arquivo do kit ou de um artigo, lido uma vez por processo."""
    return (_AQUI / nome).read_text(encoding="utf-8")


def pagina(artigo: str, script: str | None = None) -> rx.Component:
    """A página de um artigo: ``<artigo>.html`` + ``<artigo>.js`` sobre o kit.

    ``script`` troca o ``.js`` por outro, para artigos que diferem só no texto
    e compartilham os tratadores (Yvynation: TI, UC e área desenhada).

    ``data-backend`` leva a URL do backend vista na compilação; o kit a
    reescreve no navegador pela mesma regra do ``getBackendURL`` do Reflex
    (em produção, single-port, é a própria origem da página).
    """
    return rx.fragment(
        rx.el.style(ler("kit.css")),
        rx.html(
            ler(f"{artigo}.html"),
            id="rp-raiz",
            custom_attrs={"data-backend": get_config().api_url, "lang": "pt-BR"},
            on_mount=rx.call_script(ler("kit.js") + "\n" + ler(f"{script or artigo}.js")),
        ),
    )
