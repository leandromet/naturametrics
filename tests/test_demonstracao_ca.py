"""The English walkthrough (/walkthrough) on a point above Kelowna: snapshot and article.

No network: the example is the committed snapshot (scripts/build_demonstracao.py ca),
and the article checks are text checks on reportagem/naturametrics_ca.{en.html,js}.
"""

import json
import math
import re
from pathlib import Path

from naturametrics.canada.services import demonstracao

ARTIGO = Path(__file__).resolve().parent.parent / "naturametrics" / "reportagem"


def _dados():
    return json.loads(demonstracao.ARQUIVO_EXEMPLO.read_text(encoding="utf-8"))


def test_snapshot_is_clean_and_small():
    dados = _dados()
    assert dados["erros"] == {}
    assert demonstracao.ARQUIVO_EXEMPLO.stat().st_size < 120_000
    assert "camadas" not in dados
    assert (dados["ponto"]["lat"], dados["ponto"]["lon"]) == demonstracao.EXEMPLO_PADRAO


def test_land_cover_adds_up_to_each_disc():
    """Pixel count × pixel area on one grid (canada aci_history._pixel_area_call):
    with the area from a lat/long grid, every disc summed a third short."""
    h = _dados()["historico"]
    for raio, classes in h["raios"].items():
        soma = sum(serie[-1] for serie in classes.values())
        disco = math.pi * float(raio) ** 2 * 100
        assert abs(soma - disco) / disco < 0.03, (raio, soma, disco)


def test_every_step_has_a_handler():
    html = (ARTIGO / "naturametrics_ca.en.html").read_text(encoding="utf-8")
    js = (ARTIGO / "naturametrics_ca.js").read_text(encoding="utf-8")
    passos = re.findall(r'data-passo="([a-z0-9_-]+)"', html)
    assert len(passos) == 9
    assert [p for p in passos if not re.search(rf"\b{re.escape(p)}: function", js)] == []
    assert set(passos) <= set(re.findall(r'id="camada-([a-z0-9_-]+)"', html))
    assert sorted(set(re.findall(r'data-nota="(\d+)"', html))) == sorted(set(re.findall(r'id="nota-(\d+)"', html)))


def test_pages_render():
    from naturametrics.pages.demonstracao import walkthrough, walkthrough_brasil

    walkthrough().render()
    walkthrough_brasil().render()
