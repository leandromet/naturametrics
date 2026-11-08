"""The rows of the "Climate" tab: climate, fire weather, Köppen class and relief at a point.

Pure formatting over the readers (``climate_blocks`` for the world blocks, ``glc_earth.terrain`` for
Copernicus relief), so it can be tested with stubs and carries no Earth Engine or Reflex state.
Each row is a ``{"k": label, "v": value, "style": ""|"head"|"sub"|"muted"}`` dict the tab renders.
"""

from __future__ import annotations

from typing import Any

from . import climate_blocks, glc_earth

TEXT: dict[str, dict[str, str]] = {
    "en": {
        "terrain": "Terrain (Copernicus GLO-30)", "elev": "Elevation", "slope": "Mean slope",
        "koppen": "Climate class (Köppen-Geiger)", "today": "today",
        "ssp245": "2041–2070, SSP2-4.5", "ssp585": "2041–2070, SSP5-8.5",
        "climate": "Climate and fire weather, median of nine models",
        "nodata": "No climate data for this point (sea, or outside the built world).",
        "sources": "Sources: NASA NEX-GDDP-CMIP6 and NEX-GDDP-FWI (0.5° and 0.25° cells), Beck et al. 2023 (Köppen-Geiger, 1 km), Copernicus GLO-30. Relief is read over a 5 km circle.",
    },
    "pt": {
        "terrain": "Relevo (Copernicus GLO-30)", "elev": "Altitude", "slope": "Declive médio",
        "koppen": "Classe climática (Köppen-Geiger)", "today": "hoje",
        "ssp245": "2041–2070, SSP2-4.5", "ssp585": "2041–2070, SSP5-8.5",
        "climate": "Clima e perigo de fogo, mediana de nove modelos",
        "nodata": "Sem dados de clima para este ponto (mar, ou fora do mundo construído).",
        "sources": "Fontes: NASA NEX-GDDP-CMIP6 e NEX-GDDP-FWI (células de 0,5° e 0,25°), Beck et al. 2023 (Köppen-Geiger, 1 km), Copernicus GLO-30. O relevo é lido num círculo de 5 km.",
    },
}

IND: dict[str, dict[str, str]] = {
    "en": {"tmean": "Mean temperature", "hot_days": "Hot days", "precip": "Rainfall", "dry_days": "Dry days",
           "heavy_days": "Heavy-rain days", "txx": "Hottest day", "rx1day": "Wettest day",
           "water_balance": "Water balance", "fwi": "Fire weather index", "fwi_n30": "Days FWI > 30",
           "fwi_np95": "Days above the local 95th percentile"},
    "pt": {"tmean": "Temperatura média", "hot_days": "Dias quentes", "precip": "Chuva", "dry_days": "Dias secos",
           "heavy_days": "Dias de chuva forte", "txx": "Dia mais quente", "rx1day": "Dia mais chuvoso",
           "water_balance": "Balanço hídrico", "fwi": "Índice de perigo de fogo", "fwi_n30": "Dias com FWI > 30",
           "fwi_np95": "Dias acima do 95º percentil local"},
}


def _fmt(x: float, digits: int = 1) -> str:
    return f"{x:,.{digits}f}".replace(",", " ")


def _signed(x: float, digits: int = 1) -> str:
    return f"{'+' if x >= 0 else ''}{_fmt(x, digits)}"


def build_rows(lat: float, lon: float, lang: str = "en") -> list[dict[str, str]]:
    """Terrain, climate (SSP2-4.5 and SSP5-8.5), fire weather and Köppen at a point."""
    lang = "pt" if lang == "pt" else "en"
    tr, ind = TEXT[lang], IND[lang]
    clim = climate_blocks.point(lat, lon)
    ter = glc_earth.terrain(lat, lon)
    if clim is None and ter is None:
        return [{"k": "", "v": tr["nodata"], "style": "muted"}]
    rows: list[dict[str, str]] = []
    if ter is not None:
        rows.append({"k": tr["terrain"], "v": "", "style": "head"})
        rows.append({"k": tr["elev"], "style": "", "v": f"{_fmt(ter['elev_min'], 0)} · "
                     f"{_fmt(ter['elev_mean'], 0)} · {_fmt(ter['elev_max'], 0)} m"})
        if ter.get("slope") is not None:
            rows.append({"k": tr["slope"], "v": f"{_fmt(ter['slope'])}°", "style": ""})
    if clim is not None:
        rows.append({"k": tr["climate"], "v": f"{clim['models']} · {clim['step']}°", "style": "head"})
        for scen in ("ssp245", "ssp585"):
            rows.append({"k": tr[scen], "v": "", "style": "sub"})
            for r in clim[scen]:
                change = (f"{_signed(r['change'], 0)} %" if r["kind"] == "pct" else _signed(r["change"]))
                rows.append({"k": ind.get(r["key"], r["key"]), "style": "",
                             "v": f"{_fmt(r['baseline'])} → {_fmt(r['future'])} {r['unit']} ({change})"})
        kop = clim.get("koppen") or {}
        if kop:
            rows.append({"k": tr["koppen"], "v": "", "style": "head"})
            for period in ("base", "ssp245", "ssp585"):
                if period in kop:
                    c = kop[period]
                    label = tr["today"] if period == "base" else tr[period]
                    rows.append({"k": label, "v": f"{c['sym']} · {c[lang]}", "style": ""})
    rows.append({"k": "", "v": tr["sources"], "style": "muted"})
    return rows
