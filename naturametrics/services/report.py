"""A single, self-contained HTML report — figures and tables laid out for
reading (or printing to PDF) the way a manuscript's site-characterisation
section would be, rather than five separate chart screenshots pasted in by
hand.

This is the third of three complementary export paths, not a replacement for
either of the other two:

* the per-chart/per-table icons in ``components/results.py`` — reach for one
  figure or one table at a time, no document in between;
* the ODS workbook (``services.exports``) — every number, in a shape meant to
  be reprocessed, not read;
* this report — the "send someone everything, already laid out" case.

Plotly is embedded **inline** (its ~4.5 MB bundle written into the page once,
reused by every figure after the first via ``include_plotlyjs=False``), not
through a CDN and not rasterised via kaleido: the report has to open
standalone — emailed, archived, opened offline years later — and kaleido
pulls in a headless-Chromium dependency this app does not otherwise carry
(see services/connectivity.py's own reasoning for staying off exactly that
dependency).

Figures first, tables after, on the *same* page rather than two files: one
attachment beats two (the same reasoning services/exports.py gives for one
ODS with tabs over a ZIP of CSVs), and a print-CSS page break between the two
sections still gives a reader who prints to PDF the "figures on their own
pages, then tables" feel without needing a second download.
"""

from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import plotly.io as pio

from ..components import charts
from ..config import mapbiomas as mb
from ..config.citation import APP_URL, CITATION_TEXT, DATA_SOURCES
from ..config.settings import BUFFER_RADII_KM
from .buffers import BufferShape
from .change_mask import FOREST_CODE_BASELINE_YEAR
from .connectivity import CONNECTIVITY_COLUMNS
from .exports import PIXEL_CAVEAT, _buffer_summary, _provenance_rows
from .geo import Point
from .landscape_metrics import METRIC_COLUMNS
from .provenance import Provenance

logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"

_METRIC_HEADERS_PT = {
    "radius_km": "Buffer (km)", "area_ha": "Área (ha)", "patches": "Manchas",
    "patch_density": "Manchas/ha", "largest_patch_ha": "Maior mancha (ha)",
    "largest_patch_pct": "Maior mancha (%)", "edge_m": "Borda (m)",
    "edge_density": "Borda (m/ha)", "mean_patch_ha": "Mancha média (ha)",
    "patch_area_sq_ha": "Σ área² (ha²)", "meff_ha": "Meff (ha)",
    "shannon": "Shannon", "simpson": "Simpson", "simpson_evenness": "Equidade",
}
_CONNECTIVITY_HEADERS_PT = {
    "radius_km": "Buffer (km)", "n_fragments": "Fragmentos",
    "enn_mean_m": "Dist. média viz. mais próx. (m)", "enn_median_m": "Mediana (m)",
}
_SUMMARY_HEADERS_PT = {
    "radius_km": "Buffer (km)", "classe_pt": "Classe",
    "area_primeiro_ano_ha": f"Área {mb.MAPBIOMAS_YEAR_START} (ha)",
    "area_ultimo_ano_ha": f"Área {mb.MAPBIOMAS_YEAR_END} (ha)",
    "variacao_ha": "Variação (ha)", "variacao_pct": "Variação (%)",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _esc(value: Any) -> str:
    """Bare-minimum HTML-escaping for a cell/heading. Every value here comes
    from a computed number, a class label or this app's own identity strings
    — never third-party free text — but escaping costs nothing, and a stray
    "<" in a place name should not be able to break the page."""
    if isinstance(value, float):
        value = f"{value:,.2f}".rstrip("0").rstrip(".")
    return html.escape(str(value))


def _table_html(df: pd.DataFrame, headers: dict[str, str],
                caption: str, empty_note: str) -> str:
    if df is None or df.empty:
        return f'<p class="nm-figure-caption">{_esc(caption)}</p><p class="nm-empty">{_esc(empty_note)}</p>'
    cols = [c for c in headers if c in df.columns]
    head = "".join(f"<th>{_esc(headers[c])}</th>" for c in cols)
    rows = "".join(
        "<tr>" + "".join(f"<td>{_esc(row[c])}</td>" for c in cols) + "</tr>"
        for _, row in df.iterrows()
    )
    return (
        f'<p class="nm-figure-caption">{_esc(caption)}</p>'
        f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"
    )


def _fig_html(fig, div_id: str, first: bool) -> str:
    return pio.to_html(
        fig, full_html=False, include_plotlyjs=("inline" if first else False),
        div_id=div_id,
        config={"displayModeBar": False, "displaylogo": False, "responsive": True},
    )


_CSS = """
:root { color-scheme: light; }
body { font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
       color: #1a1a1a; max-width: 960px; margin: 2rem auto; padding: 0 1.5rem;
       line-height: 1.5; }
h1 { font-size: 1.4rem; margin-bottom: 0.2rem; }
h2 { font-size: 1.1rem; margin-top: 2.5rem; border-bottom: 2px solid #1f8d49;
     padding-bottom: 0.3rem; }
h3 { font-size: 0.95rem; margin-top: 1.75rem; color: #333; }
.nm-subtitle { color: #666; font-size: 0.9rem; margin-top: 0; }
.nm-meta { font-size: 0.82rem; color: #555; }
.nm-meta dt { font-weight: 600; display: inline; }
.nm-meta dd { display: inline; margin: 0 1.2rem 0 0.3rem; }
.nm-figure-caption { font-size: 0.85rem; font-weight: 600; margin: 0 0 0.3rem 0; }
.nm-caveat { font-size: 0.78rem; color: #a15c00; background: #fff8e6;
             border: 1px solid #f0d59b; border-radius: 4px; padding: 0.5rem 0.75rem;
             margin: 0.5rem 0 1.5rem 0; }
table { border-collapse: collapse; width: 100%; font-size: 0.8rem; margin-bottom: 1.5rem; }
th, td { border: 1px solid #ddd; padding: 0.3rem 0.5rem; text-align: right; }
th { background: #f3f3f3; text-align: right; }
th:first-child, td:first-child { text-align: left; }
.nm-empty { color: #888; font-size: 0.85rem; }
.nm-footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #ddd;
             font-size: 0.78rem; color: #555; }
.nm-footer ul { padding-left: 1.2rem; }
@media print {
  body { max-width: none; margin: 0; padding: 0 0.5in; }
  h2.nm-page-break { page-break-before: always; }
  table { font-size: 9pt; }
}
"""


def study_point_report_html(
    p: Point,
    history: pd.DataFrame,
    history_prov: Provenance,
    identity: dict[str, Any] | None = None,
    age_buffers: pd.DataFrame | None = None,
    age_buffers_prov: Provenance | None = None,
    change: dict[float, dict[str, float]] | None = None,
    landscape_metrics: pd.DataFrame | None = None,
    landscape_metrics_prov: Provenance | None = None,
    connectivity: pd.DataFrame | None = None,
    connectivity_prov: Provenance | None = None,
    biomass: pd.DataFrame | None = None,
    biomass_prov: Provenance | None = None,
    buffer_shape: BufferShape = "circle",
    include_figures: bool = True,
    include_tables: bool = True,
    lang: str = "pt",
) -> tuple[bytes, str]:
    """One HTML page for the study point currently on screen.

    Takes the same already-computed frames ``study_point_workbook`` does
    (nothing here is recomputed — same reasoning as that function's own
    docstring, doc/11 §5), plus ``include_figures``/``include_tables`` so a
    user can ask for either half alone.
    """
    identity = identity or {}
    history = history if history is not None else pd.DataFrame()
    age_buffers = age_buffers if age_buffers is not None else pd.DataFrame()
    change = change or {}
    landscape_metrics = (landscape_metrics if landscape_metrics is not None
                         else pd.DataFrame())
    connectivity = connectivity if connectivity is not None else pd.DataFrame()
    biomass = biomass if biomass is not None else pd.DataFrame()
    radii = sorted(BUFFER_RADII_KM)

    title = "Relatório de local — Naturametrics" if lang == "pt" \
        else "Site report — Naturametrics"
    parts: list[str] = [f"<h1>{_esc(title)}</h1>"]

    subtitle_bits = [f"{p.lat:.5f}, {p.lon:.5f}"]
    if identity.get("conglomerado"):
        subtitle_bits.append(str(identity["conglomerado"]))
    if identity.get("municipio"):
        subtitle_bits.append(f"{identity['municipio']}/{identity.get('uf', '')}")
    parts.append(f'<p class="nm-subtitle">{_esc(" · ".join(subtitle_bits))}</p>')

    parts.append('<dl class="nm-meta">')
    meta_rows = [
        ("Gerado em (UTC)" if lang == "pt" else "Generated (UTC)", _now_iso()),
        ("Raios dos buffers (km)" if lang == "pt" else "Buffer radii (km)",
         ", ".join(f"{r:g}" for r in radii)),
        ("Formato dos buffers" if lang == "pt" else "Buffer shape", buffer_shape),
        ("Anos (uso da terra)" if lang == "pt" else "Years (land use)",
         f"{mb.MAPBIOMAS_YEAR_START}–{mb.MAPBIOMAS_YEAR_END}"),
    ]
    for k, v in meta_rows:
        parts.append(f"<dt>{_esc(k)}:</dt><dd>{_esc(v)}</dd>")
    parts.append("</dl>")

    fig_count = 0
    first_fig = True

    def add_figure(fig, div_prefix: str, caption: str) -> None:
        nonlocal fig_count, first_fig
        fig_count += 1
        parts.append(f'<p class="nm-figure-caption">'
                     f'{"Figura" if lang == "pt" else "Figure"} {fig_count}. '
                     f'{_esc(caption)}</p>')
        parts.append(_fig_html(fig, f"{div_prefix}-{fig_count}", first_fig))
        first_fig = False

    if include_figures:
        parts.append(f'<h2>{"Figuras" if lang == "pt" else "Figures"}</h2>')
        if not history.empty:
            for r in radii:
                add_figure(
                    charts.land_cover_history_figure(history, r, lang=lang),
                    "nm-hist",
                    (f"Histórico de uso e cobertura da terra — buffer de {r:g} km."
                     if lang == "pt" else
                     f"Land use and cover history — {r:g} km buffer."),
                )
        else:
            parts.append(f'<p class="nm-empty">'
                         f'{"Histórico de uso da terra não disponível." if lang == "pt" else "Land-cover history not available."}'
                         f"</p>")

        if not age_buffers.empty:
            for r in radii:
                add_figure(
                    charts.forest_age_histogram_figure(age_buffers, r, lang=lang),
                    "nm-age",
                    (f"Idade da vegetação nativa — buffer de {r:g} km."
                     if lang == "pt" else
                     f"Native vegetation age — {r:g} km buffer."),
                )

        if not biomass.empty:
            for r in radii:
                add_figure(
                    charts.biomass_history_figure(biomass, r, lang=lang),
                    "nm-biomass",
                    (f"Biomassa acima do solo (ESA CCI) — buffer de {r:g} km."
                     if lang == "pt" else
                     f"Above-ground biomass (ESA CCI) — {r:g} km buffer."),
                )

        if fig_count == 0:
            parts.append(f'<p class="nm-empty">'
                         f'{"Nenhuma figura disponível ainda." if lang == "pt" else "No figures available yet."}'
                         f"</p>")

    table_count = 0

    def add_table(df: pd.DataFrame, headers: dict[str, str], caption: str,
                  empty_note: str) -> None:
        nonlocal table_count
        table_count += 1
        prefix = "Tabela" if lang == "pt" else "Table"
        parts.append(_table_html(df, headers, f"{prefix} {table_count}. {caption}",
                                 empty_note))

    if include_tables:
        heading_class = ' class="nm-page-break"' if include_figures else ""
        parts.append(f'<h2{heading_class}>{"Tabelas" if lang == "pt" else "Tables"}</h2>')
        parts.append(f'<div class="nm-caveat">{_esc(PIXEL_CAVEAT)}</div>')

        summary = _buffer_summary(history)
        add_table(
            summary, _SUMMARY_HEADERS_PT,
            (f"Variação de área por classe, {mb.MAPBIOMAS_YEAR_START}–"
             f"{mb.MAPBIOMAS_YEAR_END}, por buffer." if lang == "pt" else
             f"Area change by class, {mb.MAPBIOMAS_YEAR_START}–"
             f"{mb.MAPBIOMAS_YEAR_END}, per buffer."),
            "Histórico de uso da terra não disponível." if lang == "pt"
            else "Land-cover history not available.",
        )

        if change:
            change_rows = pd.DataFrame.from_records([
                {"radius_km": r, "perda_ha": round(v["loss_ha"], 2),
                 "regeneracao_ha": round(v["gain_ha"], 2),
                 "estavel_ha": round(v["stable_ha"], 2)}
                for r, v in sorted(change.items())
            ])
            add_table(
                change_rows,
                {"radius_km": "Buffer (km)", "perda_ha": "Perda (ha)",
                 "regeneracao_ha": "Regeneração (ha)", "estavel_ha": "Estável (ha)"}
                if lang == "pt" else
                {"radius_km": "Buffer (km)", "perda_ha": "Loss (ha)",
                 "regeneracao_ha": "Regrowth (ha)", "estavel_ha": "Stable (ha)"},
                (f"Perda/regeneração de vegetação natural desde "
                 f"{FOREST_CODE_BASELINE_YEAR} (marco do Código Florestal)."
                 if lang == "pt" else
                 f"Natural-vegetation loss/regrowth since {FOREST_CODE_BASELINE_YEAR} "
                 f"(Forest Code baseline)."),
                "",
            )

        add_table(
            landscape_metrics, _METRIC_HEADERS_PT,
            "Métricas de paisagem por buffer." if lang == "pt"
            else "Landscape metrics per buffer.",
            "Métricas de paisagem não calculadas." if lang == "pt"
            else "Landscape metrics not computed.",
        )

        if not connectivity.empty:
            add_table(
                connectivity, _CONNECTIVITY_HEADERS_PT,
                ("Conectividade entre fragmentos de floresta — distância ao "
                 "vizinho mais próximo (ENN)." if lang == "pt" else
                 "Forest-fragment connectivity — nearest-neighbour distance (ENN)."),
                "",
            )

    # Constraint C6 (doc/01-premises.md), in this medium too: every number
    # above must be traceable to the dataset/reducer/scale that produced it —
    # same _provenance_rows the ODS metadata sheet uses (services.exports),
    # just rendered as a table instead of spreadsheet rows.
    provenances = [history_prov, age_buffers_prov, landscape_metrics_prov,
                  connectivity_prov, biomass_prov]
    provenances = [pr for pr in provenances if pr is not None]
    if provenances:
        parts.append(f'<h2>{"Proveniência" if lang == "pt" else "Provenance"}</h2>')
        prov_rows = [row for pr in provenances for row in _provenance_rows(pr)]
        head = ("<th>Campo</th><th>Valor</th>" if lang == "pt"
               else "<th>Field</th><th>Value</th>")
        body = "".join(
            f"<tr><td>{_esc(k)}</td><td>{_esc(v)}</td></tr>" for k, v in prov_rows)
        parts.append(f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")

    parts.append('<div class="nm-footer">')
    parts.append(f"<p>{_esc(CITATION_TEXT)}</p>")
    parts.append("<ul>")
    for name, detail, url in DATA_SOURCES:
        parts.append(f'<li>{_esc(name)} — {_esc(detail)} '
                     f'<a href="{_esc(url)}">{_esc(url)}</a></li>')
    parts.append("</ul>")
    parts.append(f'<p><a href="{_esc(APP_URL)}">{_esc(APP_URL)}</a> · '
                 f"Naturametrics v{APP_VERSION}</p>")
    parts.append("</div>")

    doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head><body>"
        + "".join(parts) + "</body></html>"
    )

    label = identity.get("conglomerado") or f"{p.lat:.4f}_{p.lon:.4f}".replace("-", "s")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"naturametrics_relatorio_{label}_{ts}.html"
    data = doc.encode("utf-8")
    logger.info("Study-point report: %s (%s KiB, %s figures, %s tables)",
               name, len(data) // 1024, fig_count, table_count)
    return data, name
