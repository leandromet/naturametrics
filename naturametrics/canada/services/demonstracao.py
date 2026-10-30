"""The numbers of the Canada walkthrough (``/walkthrough``, Kelowna).

The English walkthrough opens a point in the forest above Kelowna instead of a
Brazilian forest-inventory plot, so Canadian readers see land they know. Like
the Brazil package (``naturametrics/services/demonstracao.py``) it has no
numbers of its own: it is built by the same services the Canada page runs on a
click — AAFC crop-inventory history by disc, the point's own pixel, NTEMS stand
age, and Hansen loss and gain — for one example point (or another, by
``?lat=&lon=``). If a number on the page disagrees with the app, the defect is
here, not in the text.

Measured on the example (2026-10-29): ~8 s cold with the calls in parallel. The
example is stored so the page opens at once; tile URLs are minted per request.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ...config.settings import BUFFER_RADII_KM
from ...services.demonstracao import PontoInvalido, _prov, _r, _seguro
from ...services.geo import point
from ..config import aafc
from ..config.forest import HANSEN_TREECOVER_THRESHOLD
from . import aci_history, forest, layers
from .geo import validate_for_analysis

logger = logging.getLogger(__name__)

#: A 94-year-old conifer stand on the lower slopes of Myra-Bellevue, above the
#: East Kelowna orchards: forest at the point, orchards and suburbs within 5 km,
#: and the 2003 Okanagan Mountain Park fire's scar inside the 10 km disc.
EXEMPLO_PADRAO = (49.825, -119.35)
#: The radius the page uses when a step shows a single zone.
RAIO_PRINCIPAL = 5.0

ROTA = "/_demonstracao/naturametrics_ca.json"

ARQUIVO_EXEMPLO = Path(__file__).resolve().parents[3] / "data" / "demonstracao" / "naturametrics_ca.json"

_TTL_S = 6 * 3600
_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
_travas: Dict[str, threading.Lock] = {}
_trava_global = threading.Lock()


def _trava(chave: str) -> threading.Lock:
    with _trava_global:
        return _travas.setdefault(chave, threading.Lock())


def _historico(df) -> Dict[str, Any]:
    anos = sorted(int(a) for a in df["year"].unique())
    por_raio: Dict[str, Dict[str, list]] = {}
    classes: Dict[str, Dict[str, str]] = {}
    for (raio, classe), g in df.groupby(["radius_km", "class_id"]):
        serie = dict(zip(g["year"].astype(int), g["area_ha"].astype(float)))
        por_raio.setdefault(_r(raio), {})[str(int(classe))] = [round(serie.get(a, 0.0), 2) for a in anos]
        if str(int(classe)) not in classes:
            linha = g.iloc[0]
            classes[str(int(classe))] = {"nome": str(linha["class_pt"]), "nome_en": str(linha["class_en"]),
                                         "cor": str(linha["color"])}
    return {"anos": anos, "raios": por_raio, "classes": classes,
            "nativas": sorted(aafc.NATURAL_VEGETATION)}


def _ponto(lat: Optional[float], lon: Optional[float]) -> tuple[float, float]:
    if lat is None or lon is None:
        return EXEMPLO_PADRAO
    try:
        validate_for_analysis(point(lat=lat, lon=lon))
    except Exception as exc:  # the message is already written for the reader
        raise PontoInvalido(str(exc)) from exc
    return lat, lon


def _calcular(lat: float, lon: float) -> Dict[str, Any]:
    p = point(lat=lat, lon=lon)
    raios = tuple(BUFFER_RADII_KM)
    erros: Dict[str, str] = {}
    tarefas: Dict[str, Callable[[], Any]] = {
        "historico": lambda: aci_history.land_cover_history(p, raios),
        "pixel": lambda: aci_history.pixel_series(p),
        "idade": lambda: forest.buffer_forest_age(p, raios),
        "idade_ponto": lambda: forest.point_forest_age(p),
        "mudanca": lambda: forest.change_stats(p, raios),
        "perda": lambda: forest.loss_by_year(p, RAIO_PRINCIPAL),
    }
    with ThreadPoolExecutor(max_workers=len(tarefas)) as pool:
        futuros = {k: pool.submit(_seguro, k, fn, erros) for k, fn in tarefas.items()}
        r = {k: f.result() for k, f in futuros.items()}

    out: Dict[str, Any] = {
        "ponto": {"lat": lat, "lon": lon},
        "raios": [_r(x) for x in raios],
        "raio_principal": _r(RAIO_PRINCIPAL),
        "procedencia": [],
        "erros": erros,
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if r["historico"]:
        df, pr = r["historico"]
        out["historico"] = _historico(df)
        out["procedencia"].append(_prov(pr))
    if r["pixel"]:
        df, pr = r["pixel"]
        out["pixel"] = [{"ano": int(x.year), "classe": int(x.class_id), "nome": str(x.class_pt),
                         "nome_en": str(x.class_en), "cor": str(x.color)}
                        for x in df.itertuples() if x.class_id == x.class_id]
        out["procedencia"].append(_prov(pr))
    if r["idade"]:
        df, pr = r["idade"]
        out["idade"] = {
            "resumo": {_r(x): forest.age_summary(df, x) for x in raios},
            "classes": {_r(raio): [{"faixa": str(g.bin), "cor": str(g.color), "ha": round(float(g.area_ha), 2)}
                                   for g in grp.itertuples()]
                        for raio, grp in df.groupby("radius_km")},
        }
        out["procedencia"].append(_prov(pr))
    if r["idade_ponto"]:
        dados, pr = r["idade_ponto"]
        out["idade_ponto"] = dados
    if r["mudanca"]:
        dados, pr = r["mudanca"]
        out["mudanca"] = {"limiar_pct": HANSEN_TREECOVER_THRESHOLD, "raios": dados}
        out["procedencia"].append(_prov(pr))
    if r["perda"]:
        df, pr = r["perda"]
        out["perda"] = [{"ano": int(x.year), "ha": round(float(x.loss_ha), 2)} for x in df.itertuples()]
        out["procedencia"].append(_prov(pr))
    return out


def _camadas(pacote: Dict[str, Any]) -> Dict[str, Any]:
    """The same tiles as the Canada page's layer panel."""
    anos = (pacote.get("historico") or {}).get("anos") or [aafc.ACI_YEAR_END]
    specs: Dict[str, Callable[[], Any]] = {
        f"aci_{anos[0]}": lambda: layers.aci_spec(anos[0]),
        f"aci_{anos[-1]}": lambda: layers.aci_spec(anos[-1]),
        "idade": lambda: layers.forest_age_spec(),
        "hansen": lambda: layers.hansen_change_spec(2001, HANSEN_TREECOVER_THRESHOLD),
    }
    erros: Dict[str, str] = {}
    out: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=len(specs)) as pool:
        futuros = {k: pool.submit(_seguro, f"layer {k}", fn, erros) for k, fn in specs.items()}
        for k, f in futuros.items():
            spec = f.result()
            if spec and spec.get("url"):
                out[k] = {"url": spec["url"], "attribution": spec.get("attribution", ""),
                          "opacity": spec.get("opacity", 0.8)}
    return out


def instantaneo() -> Dict[str, Any]:
    """The example's package without layers — ``ARQUIVO_EXEMPLO``."""
    return _calcular(*EXEMPLO_PADRAO)


def _exemplo_guardado() -> Optional[Dict[str, Any]]:
    try:
        return json.loads(ARQUIVO_EXEMPLO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def pacote(lat: Optional[float] = None, lon: Optional[float] = None) -> Dict[str, Any]:
    """The whole package for one point, from the cache when possible."""
    lat, lon = _ponto(lat, lon)
    exemplo = (lat, lon) == EXEMPLO_PADRAO
    if exemplo:
        guardado = _exemplo_guardado()
        if guardado:
            return {**guardado, "camadas": _camadas(guardado), "exemplo_padrao": True}
    chave = f"{lat:.5f},{lon:.5f}"
    with _trava(chave):
        guardado = _cache.get(chave)
        if guardado and time.time() - guardado[0] < _TTL_S:
            dados = guardado[1]
        else:
            t0 = time.time()
            dados = _calcular(lat, lon)
            logger.info("walkthrough %s computed in %.1f s", chave, time.time() - t0)
            if not dados["erros"]:
                _cache[chave] = (time.time(), dados)
    return {**dados, "camadas": _camadas(dados), "exemplo_padrao": exemplo}
