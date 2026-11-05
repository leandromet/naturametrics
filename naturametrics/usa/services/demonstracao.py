"""The numbers of the USA walkthrough (``/walkthrough/usa``, Paradise CA).

Like the Canada and Brazil packages it has no numbers of its own: it is built by the same
services the USA page runs on a click — Annual NLCD history by disc, the point's own pixel, LCMS
disturbance history, MTBS fire severity, time since disturbance, tree canopy and Hansen loss — for
one example point (or another, by ``?lat=&lon=``). If a number on the page disagrees with the app,
the defect is here, not in the text.

The example is **Paradise, California**: a town of conifer forest on a ridge above the Feather River
canyon, burned almost entirely by the Camp Fire of November 2018. Every panel has something to say
about it — LCMS books the change in 2019, MTBS in 2018, the canopy falls by half, and the forest
that is left is "6 to 10 years since disturbance".
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
from ..config import disturbance as dcfg
from ..config import nlcd
from ..config.forest import HANSEN_TREECOVER_THRESHOLD
from . import disturbance, forest, layers, nlcd_history
from .geo import region_of, validate_for_analysis

logger = logging.getLogger(__name__)

EXEMPLO_PADRAO = (39.76, -121.62)
RAIO_PRINCIPAL = 5.0

ROTA = "/_demonstracao/naturametrics_us.json"
ARQUIVO_EXEMPLO = Path(__file__).resolve().parents[3] / "data" / "demonstracao" / "naturametrics_us.json"

_TTL_S = 6 * 3600
_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
_travas: Dict[str, threading.Lock] = {}
_trava_global = threading.Lock()


def _trava(chave: str) -> threading.Lock:
    with _trava_global:
        return _travas.setdefault(chave, threading.Lock())


def _historico(df, nativas=None) -> Dict[str, Any]:
    """Long frame (radius, year, class) → ``{anos, raios: {r: {class: [ha per year]}}, classes}``."""
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
    out = {"anos": anos, "raios": por_raio, "classes": classes}
    if nativas is not None:
        out["nativas"] = sorted(nativas)
    return out


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
        "historico": lambda: nlcd_history.land_cover_history(p, raios),
        "pixel": lambda: nlcd_history.pixel_series(p),
        "disturbio": lambda: disturbance.disturbance_history(p, raios),
        "fogo": lambda: disturbance.fire_history(p, raios),
        "idade": lambda: disturbance.time_since_disturbance(p, raios),
        "dossel": lambda: disturbance.canopy_history(p, raios),
        "perda": lambda: forest.loss_by_year(p, RAIO_PRINCIPAL),
    }
    with ThreadPoolExecutor(max_workers=len(tarefas)) as pool:
        futuros = {k: pool.submit(_seguro, k, fn, erros) for k, fn in tarefas.items()}
        r = {k: f.result() for k, f in futuros.items()}

    out: Dict[str, Any] = {
        "ponto": {"lat": lat, "lon": lon},
        "regiao": region_of(p) or "conus",
        "raios": [_r(x) for x in raios],
        "raio_principal": _r(RAIO_PRINCIPAL),
        "procedencia": [],
        "erros": erros,
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if r["historico"]:
        df, pr = r["historico"]
        if not df.empty:
            out["historico"] = _historico(df, nlcd.NATURAL_VEGETATION)
            out["procedencia"].append(_prov(pr))
    if r["pixel"]:
        df, pr = r["pixel"]
        out["pixel"] = [{"ano": int(x.year), "classe": int(x.class_id), "nome": str(x.class_pt),
                         "nome_en": str(x.class_en), "cor": str(x.color)}
                        for x in df.itertuples() if x.class_id == x.class_id]
        out["procedencia"].append(_prov(pr))
    if r["disturbio"]:
        df, pr = r["disturbio"]
        out["disturbio"] = _historico(df) if not df.empty else None
        out["procedencia"].append(_prov(pr))
    if r["fogo"]:
        df, pr = r["fogo"]
        out["fogo"] = _historico(df) if not df.empty else None
        out["procedencia"].append(_prov(pr))
    if r["idade"]:
        df, pr = r["idade"]
        out["idade"] = {"classes": {_r(raio): [{"faixa": str(g.bin), "cor": str(g.color), "ha": round(float(g.area_ha), 2)}
                                               for g in grp.itertuples()]
                                    for raio, grp in df.groupby("radius_km")},
                        "ordem": dcfg.AGE_ORDER}
        out["procedencia"].append(_prov(pr))
    if r["dossel"]:
        df, pr = r["dossel"]
        out["dossel"] = {"anos": sorted(int(a) for a in df["year"].unique()),
                         "raios": {_r(raio): [round(float(v), 2) for v in grp.sort_values("year")["canopy_pct"]]
                                   for raio, grp in df.groupby("radius_km")}}
        out["procedencia"].append(_prov(pr))
    if r["perda"]:
        df, pr = r["perda"]
        out["perda"] = [{"ano": int(x.year), "ha": round(float(x.loss_ha), 2)} for x in df.itertuples()]
        out["procedencia"].append(_prov(pr))
    out["limiar_pct"] = HANSEN_TREECOVER_THRESHOLD
    return out


def _camadas(pacote: Dict[str, Any]) -> Dict[str, Any]:
    """The same tiles as the USA page's layer panel."""
    regiao = pacote.get("regiao") or "conus"
    anos = (pacote.get("historico") or {}).get("anos") or [nlcd.NLCD_YEAR_END]
    specs: Dict[str, Callable[[], Any]] = {
        f"nlcd_{anos[0]}": lambda: layers.nlcd_spec(anos[0], region=regiao),
        f"nlcd_{anos[-1]}": lambda: layers.nlcd_spec(anos[-1], region=regiao),
        "lcms": lambda: layers.lcms_loss_spec(regiao),
        "mtbs": lambda: layers.mtbs_spec(regiao),
        "tcc_1985": lambda: layers.tcc_spec(1985, regiao),
        "tcc_2025": lambda: layers.tcc_spec(2025, regiao),
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
