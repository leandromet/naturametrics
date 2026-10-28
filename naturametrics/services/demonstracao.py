"""Os números da demonstração em rolagem (``/demonstracao``).

A página de demonstração não tem números próprios: ela pede este pacote à rota
``/_demonstracao/naturametrics.json`` e ele é montado pelos mesmos serviços que
a interface usa ao clicar num ponto — histórico MapBiomas por raio, pixel do
ponto, idade da vegetação, métricas de paisagem, biomassa, mudança desde 2008,
IBGE × MapBiomas, embargos e autos do IBAMA — para um conglomerado do IFN de
exemplo (ou outro, por ``?ifn=`` ou ``?lat=&lon=``). Se um número da
demonstração divergir do aplicativo, o defeito está aqui, não no texto.

Medido no exemplo (MT_105, Colniza/MT): ~15 s a frio, quase todo nas métricas
de paisagem (connectedComponents); o resto passa de 6 s em paralelo. Por isso o
pacote fica em memória por algumas horas, com uma trava por ponto para que dez
visitas a frio calculem uma vez só. As URLs de tiles saem de
``services/layers.py`` e têm o próprio cache, então são remontadas a cada pedido.
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

from ..config import mapbiomas as mb
from ..config.settings import BUFFER_RADII_KM
from . import auto_infracao, biomass, buffers, change_mask, embargos, ibge_vegetation, ifn
from . import landscape_metrics, layers, mapbiomas_history, vegetation_age
from .geo import point, validate_for_analysis

logger = logging.getLogger(__name__)

#: Um conglomerado no arco do desmatamento: floresta em 1985, 8% de vegetação
#: nativa no disco de 5 km em 2025, e o IBGE ainda mapeando floresta.
EXEMPLO_PADRAO = "MT_105"

ROTA = "/_demonstracao/naturametrics.json"

#: O exemplo padrão, já calculado e com geometrias leves, para a página abrir
#: na hora (a frio são ~15 s): ``scripts/build_demonstracao.py`` o regrava a
#: partir destes mesmos serviços. Outros ``?ifn=``/``?lat=`` são calculados na hora.
ARQUIVO_EXEMPLO = Path(__file__).resolve().parents[2] / "data" / "demonstracao" / "naturametrics.json"

#: O raio que a página usa quando um passo mostra uma zona só (o do texto).
RAIO_PRINCIPAL = 5.0

_TTL_S = 6 * 3600
_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
_travas: Dict[str, threading.Lock] = {}
_trava_global = threading.Lock()


class PontoInvalido(ValueError):
    """Um ``?ifn=`` que não está no catálogo, ou uma coordenada fora do Brasil."""


def _trava(chave: str) -> threading.Lock:
    with _trava_global:
        return _travas.setdefault(chave, threading.Lock())


def _prov(p: Any) -> Dict[str, Any]:
    return {
        "nome": getattr(p, "name", ""),
        "dataset": getattr(p, "dataset_id", ""),
        "escala_m": getattr(p, "scale_m", None),
        "calculado_em": getattr(p, "computed_at", ""),
    }


def _seguro(nome: str, fn: Callable[[], Any], erros: Dict[str, str]) -> Any:
    """Uma análise que falha vira uma lacuna declarada, não uma página quebrada."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        logger.exception("demonstração: %s falhou", nome)
        erros[nome] = str(exc)[:300]
        return None


def _r(v: Any) -> str:
    """Raio como chave JSON: 0.5 → "0.5", 5.0 → "5"."""
    return f"{float(v):g}"


def resolver(ifn_nome: str = "", lat: Optional[float] = None,
             lon: Optional[float] = None) -> Dict[str, Any]:
    """O ponto de estudo: um conglomerado pelo nome, ou uma coordenada."""
    if ifn_nome:
        linhas = ifn.points_named([ifn_nome.strip().upper()])
        if not linhas:
            raise PontoInvalido(f"Conglomerado {ifn_nome!r} não está no catálogo do IFN.")
        r = linhas[0]
        return {"lat": float(r["lat"]), "lon": float(r["lon"]), "conglomerado": r["conglomerado"],
                "municipio": r.get("municipio", ""), "uf": r.get("uf", ""), "bioma": r.get("bioma", ""),
                "origem": "conglomerado IFN"}
    if lat is None or lon is None:
        return resolver(EXEMPLO_PADRAO)
    try:
        validate_for_analysis(point(lat=lat, lon=lon))
    except Exception as exc:  # CoordinateError e afins: a mensagem já é para o leitor
        raise PontoInvalido(str(exc)) from exc
    return {"lat": lat, "lon": lon, "conglomerado": "", "municipio": "", "uf": "", "bioma": "",
            "origem": "coordenada"}


def _historico(df) -> Dict[str, Any]:
    anos = sorted(int(a) for a in df["year"].unique())
    por_raio: Dict[str, Dict[str, list]] = {}
    classes: Dict[str, Dict[str, str]] = {}
    for (raio, classe), g in df.groupby(["radius_km", "class_id"]):
        serie = dict(zip(g["year"].astype(int), g["area_ha"].astype(float)))
        por_raio.setdefault(_r(raio), {})[str(int(classe))] = [round(serie.get(a, 0.0), 2) for a in anos]
        if str(int(classe)) not in classes:
            linha = g.iloc[0]
            classes[str(int(classe))] = {"nome": str(linha["class_pt"]), "cor": str(linha["color"])}
    return {"anos": anos, "raios": por_raio, "classes": classes,
            "nativas": sorted(mb.NATURAL_VEGETATION)}


def _calcular(ponto: Dict[str, Any]) -> Dict[str, Any]:
    p = point(lat=ponto["lat"], lon=ponto["lon"])
    raios = tuple(BUFFER_RADII_KM)
    oeste, sul, leste, norte = buffers.disc_bounds(p, max(raios))
    erros: Dict[str, str] = {}

    tarefas = {
        "historico": lambda: mapbiomas_history.land_cover_history(p, raios),
        "pixel": lambda: mapbiomas_history.point_pixel_series(p),
        "idade_ponto": lambda: vegetation_age.point_forest_age_series(p),
        "idade": lambda: vegetation_age.buffer_forest_age_histogram(p, raios),
        "metricas": lambda: landscape_metrics.landscape_metrics(p, raios),
        "biomassa": lambda: biomass.biomass_history(p, raios),
        "mudanca": lambda: change_mask.change_stats(p, raios),
        "ibge": lambda: ibge_vegetation.mapbiomas_comparison(p, raios),
        "embargos": lambda: embargos.polygons_in_bbox(oeste, sul, leste, norte),
        "autos": lambda: auto_infracao.points_in_bbox(oeste, sul, leste, norte),
        "ifn": lambda: ifn.points_in_bbox(oeste, sul, leste, norte),
    }
    with ThreadPoolExecutor(max_workers=len(tarefas)) as pool:
        futuros = {k: pool.submit(_seguro, k, fn, erros) for k, fn in tarefas.items()}
        r = {k: f.result() for k, f in futuros.items()}

    out: Dict[str, Any] = {
        "ponto": ponto,
        "raios": [float(x) for x in raios],
        "raio_principal": RAIO_PRINCIPAL,
        "buffers": buffers.buffer_geojson(p, raios),
        "areas_ha": {_r(x): round(buffers.disc_area_ha(x), 2) for x in raios},
        "bbox": [oeste, sul, leste, norte],
        "procedencia": [],
        "erros": erros,
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    if r["historico"]:
        df, pv = r["historico"]
        out["historico"] = _historico(df)
        out["procedencia"].append(_prov(pv))
    if r["pixel"]:
        df, pv = r["pixel"]
        out["pixel"] = [{"ano": int(x.year), "classe": int(x.class_id), "nome": str(x.class_pt)}
                        for x in df.itertuples()]
    if r["idade_ponto"]:
        df, pv = r["idade_ponto"]
        out["idade_ponto"] = [{"ano": int(x.year), "idade": int(x.age), "censurado": bool(x.censored),
                               "classe": str(x.class_pt), "cor": str(x.color)} for x in df.itertuples()]
    if r["idade"]:
        df, pv = r["idade"]
        hist: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for x in df.itertuples():
            faixa = hist.setdefault(_r(x.radius_km), {}).setdefault(
                str(x.bin), {"ha": 0.0, "cor": str(x.color), "censurado": bool(x.censored), "idade_min": int(x.age)})
            faixa["ha"] = round(faixa["ha"] + float(x.area_ha), 2)
            faixa["idade_min"] = min(faixa["idade_min"], int(x.age))
        out["idade"] = {
            "faixas": {k: sorted(({"faixa": b, **v} for b, v in d.items()), key=lambda f: f["idade_min"])
                       for k, d in hist.items()},
            "resumo": {_r(x): vegetation_age.age_summary(df, x) for x in raios},
        }
        out["procedencia"].append(_prov(pv))
    if r["metricas"]:
        df, _hist, pv = r["metricas"]
        cols = ["radius_km", "area_ha", "patches", "largest_patch_pct", "edge_density", "mean_patch_ha", "meff_ha", "shannon"]
        out["metricas"] = [{c: (round(float(getattr(x, c)), 3) if getattr(x, c) is not None else None) for c in cols}
                           for x in df.itertuples()]
        out["procedencia"].append(_prov(pv))
    if r["biomassa"]:
        df, pv = r["biomassa"]
        out["biomassa"] = {
            _r(raio): [{"ano": int(x.year), "mgha": round(float(x.agb_mean_mgha), 1),
                        "sd": round(float(x.agb_sd_mgha), 1)} for x in g.itertuples()]
            for raio, g in df.groupby("radius_km")
        }
        out["procedencia"].append(_prov(pv))
    if r["mudanca"]:
        dados, pv = r["mudanca"]
        out["mudanca"] = {"de": change_mask.FOREST_CODE_BASELINE_YEAR, "ate": mb.MAPBIOMAS_YEAR_END,
                          "raios": {_r(k): {kk: round(float(vv), 1) for kk, vv in v.items()} for k, v in dados.items()},
                          "cores": {"perda": change_mask.CHANGE_COLORS[change_mask.CHANGE_LOSS],
                                    "ganho": change_mask.CHANGE_COLORS[change_mask.CHANGE_GAIN]}}
        out["procedencia"].append(_prov(pv))
    if r["ibge"]:
        df, pv = r["ibge"]
        out["ibge"] = ibge_vegetation.bucket_matrix(df, RAIO_PRINCIPAL)
        out["procedencia"].append(_prov(pv))
    for chave in ("embargos", "autos", "ifn"):
        if r[chave] is not None:
            out[chave] = _sem_identificacao(r[chave], _CAMPOS_PUBLICADOS[chave])
    return out


#: O que a demonstração mostra de cada registro. Nomes e CPF/CNPJ de autuados
#: e embargados são públicos no IBAMA e aparecem na camada do aplicativo, mas
#: uma página de demonstração, aberta por qualquer visitante, não é lugar de
#: expor pessoas: fica a data, a área e a situação.
_CAMPOS_PUBLICADOS = {
    "embargos": ("dat_embargo", "qtd_area_embargada", "sit_desmatamento", "des_tad", "municipio", "uf"),
    "autos": ("dat_hora_auto_infracao", "val_auto_infracao", "des_status_formulario", "municipio", "uf"),
    "ifn": ("conglomerado", "municipio", "uf", "bioma"),
}


def _sem_identificacao(fc: Dict[str, Any], campos: tuple[str, ...]) -> Dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": f.get("geometry"),
             "properties": {k: (f.get("properties") or {}).get(k) for k in campos}}
            for f in (fc or {}).get("features", []) if f.get("geometry")
        ],
    }


def _camadas() -> Dict[str, Any]:
    """Os mesmos tiles do painel de camadas do aplicativo."""
    ano_fim = mb.MAPBIOMAS_YEAR_END
    specs = {
        "mb_1985": lambda: layers.mapbiomas_spec(1985),
        f"mb_{ano_fim}": lambda: layers.mapbiomas_spec(ano_fim),
        "mudanca": lambda: change_mask.change_mask_spec(),
        "biomassa": lambda: layers.biomass_spec(biomass.AGB_YEARS[-1]),
        "ibge": lambda: layers.ibge_vegetation_spec(),
    }
    erros: Dict[str, str] = {}
    out: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=len(specs)) as pool:
        futuros = {k: pool.submit(_seguro, f"camada {k}", fn, erros) for k, fn in specs.items()}
        for k, f in futuros.items():
            spec = f.result()
            if spec and spec.get("url"):
                out[k] = {"url": spec["url"], "attribution": spec.get("attribution", ""),
                          "opacity": spec.get("opacity", 0.8)}
    return out


def _leve(geom: Optional[Dict[str, Any]], tol: float) -> Optional[Dict[str, Any]]:
    """Geometria para desenhar: simplificada e com 5 casas (~1 m)."""
    if not geom or not geom.get("coordinates"):
        return geom
    from shapely.geometry import mapping, shape
    g = shape(geom)
    if tol and g.geom_type != "Point":
        s = g.simplify(tol, preserve_topology=True)
        g = s if not s.is_empty else g

    def arred(c):
        return [arred(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 5), round(c[1], 5)]

    m = mapping(g)
    return {"type": m["type"], "coordinates": arred(m["coordinates"])}


def instantaneo() -> Dict[str, Any]:
    """O exemplo padrão sem camadas e com geometrias leves — o conteúdo de
    ``ARQUIVO_EXEMPLO``. Só os discos do ponto, os conglomerados e os
    registros do IBAMA do quadrado de 20 km, simplificados."""
    dados = _calcular(resolver(EXEMPLO_PADRAO))
    # só o que a página lê de cada registro (naturametrics.js, passo "ibama")
    usados = {"embargos": ("dat_embargo", "qtd_area_embargada"),
              "autos": ("dat_hora_auto_infracao", "des_status_formulario")}
    for chave, tol in (("buffers", 0.0003), ("embargos", 0.001), ("autos", 0), ("ifn", 0)):
        for f in (dados.get(chave) or {}).get("features", []):
            f["geometry"] = _leve(f.get("geometry"), tol)
            if chave in usados:
                f["properties"] = {k: f["properties"].get(k) for k in usados[chave]}
    return dados


def _exemplo_guardado() -> Optional[Dict[str, Any]]:
    try:
        return json.loads(ARQUIVO_EXEMPLO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def pacote(ifn_nome: str = "", lat: Optional[float] = None, lon: Optional[float] = None) -> Dict[str, Any]:
    """O pacote completo de um ponto, do cache quando possível."""
    if (not ifn_nome and lat is None and lon is None) or (ifn_nome or "").strip().upper() == EXEMPLO_PADRAO:
        guardado = _exemplo_guardado()
        if guardado:
            return {**guardado, "camadas": _camadas(), "exemplo_padrao": True}
    ponto = resolver(ifn_nome, lat, lon)
    chave = ponto["conglomerado"] or f"{ponto['lat']:.5f},{ponto['lon']:.5f}"
    with _trava(chave):
        guardado = _cache.get(chave)
        if guardado and time.time() - guardado[0] < _TTL_S:
            dados = guardado[1]
        else:
            t0 = time.time()
            dados = _calcular(ponto)
            logger.info("demonstração %s calculada em %.1f s", chave, time.time() - t0)
            if not dados["erros"]:
                _cache[chave] = (time.time(), dados)
    return {**dados, "camadas": _camadas(), "exemplo_padrao": chave == EXEMPLO_PADRAO}
