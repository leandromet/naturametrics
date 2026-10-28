"""The scrolling walkthrough (/demonstracao): its committed example and its article.

No network: the example is the committed snapshot (scripts/build_demonstracao.py),
and the article checks are text checks on reportagem/naturametrics.{html,js}.
"""

import json
import re
from pathlib import Path

from naturametrics.services import demonstracao

ARTIGO = Path(__file__).resolve().parent.parent / "naturametrics" / "reportagem"


def test_snapshot_is_clean_and_small():
    dados = json.loads(demonstracao.ARQUIVO_EXEMPLO.read_text(encoding="utf-8"))
    assert dados["erros"] == {}
    # the point of the snapshot is a page that opens at once
    assert demonstracao.ARQUIVO_EXEMPLO.stat().st_size < 120_000
    assert "camadas" not in dados  # tile URLs expire; they are minted per request


def test_every_step_has_a_handler():
    html = (ARTIGO / "naturametrics.html").read_text(encoding="utf-8")
    js = (ARTIGO / "naturametrics.js").read_text(encoding="utf-8")
    passos = re.findall(r'data-passo="([a-z0-9_-]+)"', html)
    assert passos
    sem = [p for p in passos if not re.search(rf"\b{re.escape(p)}: function", js)]
    assert sem == [], f"steps without a handler: {sem}"
    camadas = set(re.findall(r'id="camada-([a-z0-9_-]+)"', html))
    assert set(passos) <= camadas


def test_page_renders():
    from naturametrics.pages.demonstracao import demonstracao as pagina

    pagina().render()
