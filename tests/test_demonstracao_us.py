"""The USA walkthrough (/walkthrough/usa) on Paradise CA: snapshot and article.

No network: the example is the committed snapshot (scripts/build_demonstracao.py us), and the
article checks are text checks on reportagem/naturametrics_us.{en.html,js}.
"""

import json
import math
import re
from pathlib import Path

from naturametrics.usa.services import demonstracao

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
    """Pixel count × pixel area on one grid: each disc's classes sum to the disc's area."""
    h = _dados()["historico"]
    for raio, classes in h["raios"].items():
        soma = sum(serie[-1] for serie in classes.values())
        disco = math.pi * float(raio) ** 2 * 100
        assert abs(soma - disco) / disco < 0.03, (raio, soma, disco)


def test_the_camp_fire_shows_in_every_product():
    d = _dados()
    anos = d["fogo"]["anos"]; z = d["fogo"]["raios"]["5"]
    por_ano = [sum(z[c][i] for c in z) for i in range(len(anos))]
    assert anos[por_ano.index(max(por_ano))] == 2018                 # MTBS
    dist = d["disturbio"]; zd = dist["raios"]["5"]
    wild = zd["7"]; assert dist["anos"][wild.index(max(wild))] == 2019   # LCMS books it a year later
    canopy = d["dossel"]["raios"]["5"]; assert canopy[-1] < canopy[0] * 0.6
    assert max(d["perda"], key=lambda x: x["ha"])["ano"] in (2018, 2019)  # Hansen


def test_every_step_has_a_handler():
    html = (ARTIGO / "naturametrics_us.en.html").read_text(encoding="utf-8")
    js = (ARTIGO / "naturametrics_us.js").read_text(encoding="utf-8")
    passos = re.findall(r'data-passo="([a-z0-9_-]+)"', html)
    assert len(passos) == 11
    assert [p for p in passos if not re.search(rf"\b{re.escape(p)}: function", js)] == []
    assert set(passos) <= set(re.findall(r'id="camada-([a-z0-9_-]+)"', html))
    assert sorted(set(re.findall(r'data-nota="(\d+)"', html))) == sorted(set(re.findall(r'id="nota-(\d+)"', html)))


def test_page_renders():
    from naturametrics.pages.demonstracao import walkthrough_usa
    walkthrough_usa().render()
