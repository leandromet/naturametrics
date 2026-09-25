"""HTML renderer — the same report model as ``pdf.py``, as one self-contained page.

Figures with ``fig_json`` stay interactive (Plotly inlined once, never via a
CDN: the file must open offline years later); figures with only a PNG are
embedded as images. Each map is a single inline SVG — raster layers as
``<image>`` data URIs, outlines/rings as paths, the same furniture as the PDF.
Print CSS mirrors the PDF page so "print to PDF" from a browser looks alike.
"""

from __future__ import annotations

import base64
import html as _h
from typing import Any, List

from . import images, locator, maps, style
from .model import (Callout, Citation, ContentsList, Figure, KeyValues, LocatorMap,
                    MapComposition, MapFigure, PageBreak, Paragraph, ProvenanceTable,
                    Report, SideBySide, Table)
from .text import fmt_cell, fmt_datetime_utc, inline_markup, t

_CSS = """
:root { --accent: %(accent)s; --ink: %(ink)s; --muted: %(muted)s; --rule: %(rule)s;
        --zebra: %(zebra)s; }
* { box-sizing: border-box; }
body { font-family: 'Noto Sans', 'Segoe UI', Arial, sans-serif; color: var(--ink);
       background: #fff; max-width: 820px; margin: 2rem auto; padding: 0 16px;
       font-size: 15px; line-height: 1.45; }
.rk-app { color: var(--accent); font-weight: 700; font-size: .8rem; margin: 0; }
h1 { font-size: 1.6rem; margin: .1rem 0; }
.rk-subject { color: var(--accent); font-size: 1.15rem; margin: 0 0 .2rem; }
.rk-meta { color: var(--muted); font-size: .8rem; margin-bottom: 1.2rem; }
h2 { font-size: 1.2rem; margin: 1.8rem 0 .5rem; border-bottom: 1px solid var(--rule);
     padding-bottom: .2rem; }
p.rk-lead { font-size: 1.05rem; }
figure { margin: .8rem 0 1.1rem; }
figcaption, .rk-caption { color: var(--muted); font-size: .82rem; margin-top: .3rem; }
.rk-half { width: 48.2%%; }
.rk-row { display: flex; gap: 3.6%%; align-items: flex-start; flex-wrap: wrap; }
.rk-row > div { flex: 1 1 300px; min-width: 0; }
img.rk-img, svg.rk-map { width: 100%%; height: auto; display: block; }
.rk-placeholder { background: %(placeholder)s; color: var(--muted); font-style: italic;
                  text-align: center; padding: 2.5rem 1rem; }
table { border-collapse: collapse; width: 100%%; font-size: .82rem; margin: .3rem 0; }
th { text-align: left; border-bottom: 1.5px solid var(--ink); padding: 3px 5px; }
td { padding: 3px 5px; vertical-align: top; }
td.r, th.r { text-align: right; }
tbody tr:nth-child(even) { background: var(--zebra); }
table.rk-kv td { border-bottom: 1px solid var(--rule); background: #fff; }
table.rk-kv td:first-child { color: var(--muted); font-weight: 700; width: 36%%; }
.rk-scroll { overflow-x: auto; }
.rk-callout { padding: .55rem .8rem; margin: .6rem 0 1rem; border-left: 4px solid; }
.rk-callout.disclosure { font-weight: 700; }
.rk-legend { display: flex; flex-wrap: wrap; gap: .2rem 1rem; font-size: .75rem;
             color: var(--muted); margin-top: .3rem; }
.rk-legend i { display: inline-block; width: 12px; height: 9px; margin-right: 4px;
               vertical-align: -1px; border: 1px solid var(--rule); }
.rk-legend i.line { height: 0; border: 0; border-top: 2px solid; vertical-align: 3px; }
.rk-attr, .rk-small { color: var(--muted); font-size: .72rem; }
footer { margin-top: 2.5rem; border-top: 1px solid var(--rule); padding-top: .6rem;
         color: var(--muted); font-size: .75rem; }
@media (max-width: 600px) { body { font-size: 14px; } .rk-half { width: 100%%; } }
@media print {
  @page { size: A4; margin: 18mm 20mm; }
  body { max-width: none; margin: 0; padding: 0; font-size: 9.5pt; }
  h2 { break-after: avoid; } figure, .rk-callout { break-inside: avoid; }
  .rk-break { break-after: page; }
}
"""


def _e(text: Any) -> str:
    return _h.escape("" if text is None else str(text), quote=True)


def _data_uri(data: bytes) -> str:
    fmt, _, _ = images.image_size(data)
    mime = "image/png" if fmt == "png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _svg_path(view, geojson, polygons_only: bool = False, w: float = 1000.0,
              h: float = 1000.0) -> str:
    parts: List[str] = []
    for kind, rings in maps.iter_rings(geojson):
        if kind == "point" or (polygons_only and kind != "polygon"):
            continue
        for ring in rings:
            if len(ring) < 2:
                continue
            pts = []
            for lon, lat in ring:
                fx, fy = view.to_frac(lon, lat)
                pts.append(f"{fx * w:.1f},{fy * h:.1f}")
            parts.append("M" + " L".join(pts) + (" Z" if kind == "polygon" else ""))
    return " ".join(parts)


class _Html:
    def __init__(self, report: Report):
        self.report = report
        self.lang = report.meta.lang
        self.accent = report.meta.brand.accent
        self.n_fig = 0
        self.n_tab = 0
        self.n_map = 0
        self.plotly_needed = any(isinstance(b, Figure) and b.fig_json
                                 for b in report.blocks())

    def fig_cap(self, caption: str) -> str:
        self.n_fig += 1
        return (f"<figcaption><b>{_e(t('figure', self.lang))} {self.n_fig}</b> — "
                f"{inline_markup(caption)}</figcaption>")

    def tab_cap(self, caption: str) -> str:
        self.n_tab += 1
        return (f'<p class="rk-caption"><b>{_e(t("table", self.lang))} {self.n_tab}</b> — '
                f"{inline_markup(caption)}</p>")

    # ---- blocks -------------------------------------------------------------
    def block(self, b: Any) -> str:
        if isinstance(b, Paragraph):
            cls = ' class="rk-lead"' if b.lead else ""
            return f"<p{cls}>{inline_markup(b.text)}</p>"
        if isinstance(b, KeyValues):
            rows = "".join(f"<tr><td>{inline_markup(k)}</td><td>{inline_markup(v)}</td></tr>"
                           for k, v in b.rows)
            cap = f'<p class="rk-caption">{inline_markup(b.caption)}</p>' if b.caption else ""
            return f'<table class="rk-kv"><tbody>{rows}</tbody></table>{cap}'
        if isinstance(b, Figure):
            return self.figure(b)
        if isinstance(b, MapFigure):
            return self.map(b.composition, b.caption, True)
        if isinstance(b, LocatorMap):
            return self.map(locator.compose(b, self.accent), b.label, False)
        if isinstance(b, Table):
            return self.table(b)
        if isinstance(b, Callout):
            border, bg = style.CALLOUT_COLORS.get(b.kind, style.CALLOUT_COLORS["note"])
            title = f"<b>{inline_markup(b.title)}</b> — " if b.title else ""
            return (f'<div class="rk-callout {_e(b.kind)}" style="border-color:{border};'
                    f'background:{bg}">{title}{inline_markup(b.text)}</div>')
        if isinstance(b, ContentsList):
            head = {"pt": ["Seção", "Situação", "Observação"],
                    "es": ["Sección", "Estado", "Observación"],
                    "fr": ["Section", "Statut", "Remarque"]}.get(
                        self.lang, ["Section", "Status", "Note"])
            rows = [[i.title, t(f"status_{i.status}", self.lang), i.reason] for i in b.items]
            return self.grid(head, rows, None)
        if isinstance(b, ProvenanceTable):
            return self.provenance(b)
        if isinstance(b, Citation):
            out = [f"<p><b>{_e(t('how_to_cite', self.lang))}.</b> {inline_markup(b.text)}</p>"]
            if b.sources:
                out.append(f"<p><b>{_e(t('sources', self.lang))}</b></p><ul class='rk-small'>"
                           + "".join(f"<li>{inline_markup(s)}</li>" for s in b.sources)
                           + "</ul>")
            if b.attributions:
                out.append(f"<p><b>{_e(t('attributions', self.lang))}</b></p><ul class='rk-small'>"
                           + "".join(f"<li>{inline_markup(a)}</li>" for a in b.attributions)
                           + "</ul>")
            return "".join(out)
        if isinstance(b, SideBySide):
            return (f'<div class="rk-row"><div>{self.block(b.left)}</div>'
                    f"<div>{self.block(b.right)}</div></div>")
        if isinstance(b, PageBreak):
            return '<div class="rk-break"></div>'
        raise TypeError(f"unknown report block {type(b).__name__}")

    def figure(self, b: Figure) -> str:
        width_cls = ' class="rk-half"' if b.slot == "half" else ""
        if b.fig_json:
            import plotly.io as pio   # lazy: only reports with interactive charts need it
            page_fig = images.prepare_figure(b.fig_json, b.slot, b.aspect)
            # On screen the chart fills its column: keep the decided height,
            # drop the fixed width (a widened figure would overflow the page).
            page_fig["layout"].pop("width", None)
            page_fig["layout"]["autosize"] = True
            body = pio.to_html(page_fig,
                               include_plotlyjs=False, full_html=False,
                               config={"displayModeBar": False, "responsive": True},
                               default_width="100%")
        elif b.png:
            data = images.fit_image(b.png, style.SLOT_MM[b.slot], "flat",
                                    dpi=style.CHART_DPI)
            body = f'<img class="rk-img" alt="{_e(b.caption)}" src="{_data_uri(data)}">'
        else:
            reason = f" — {_e(b.unavailable_reason)}" if b.unavailable_reason else ""
            body = (f'<div class="rk-placeholder">{_e(t("figure_unavailable", self.lang))}'
                    f"{reason}</div>")
        return f"<figure{width_cls}>{body}{self.fig_cap(b.caption)}</figure>"

    def map(self, comp: MapComposition, caption: str, furniture: bool) -> str:
        self.n_map += 1
        view = comp.view
        W, H = 1000.0, 1000.0 * view.aspect
        slot_mm = style.SLOT_MM["full"]
        els: List[str] = []
        clip_id = f"rk-clip-{self.n_map}"
        if comp.backdrop:
            data = images.fit_image(comp.backdrop, slot_mm, "photo")
            els.append(f'<image href="{_data_uri(data)}" x="0" y="0" width="{W}" '
                       f'height="{H:.1f}" preserveAspectRatio="none"/>')
        if comp.overlays:
            clip_attr = ""
            if comp.clip_to:
                d = _svg_path(view, comp.clip_to, True, W, H)
                if d:
                    els.append(f'<clipPath id="{clip_id}"><path d="{d}" '
                               f'clip-rule="evenodd"/></clipPath>')
                    clip_attr = f' clip-path="url(#{clip_id})"'
            for ov in comp.overlays:
                data = images.fit_image(ov, slot_mm, "flat")
                els.append(f'<image href="{_data_uri(data)}" x="0" y="0" width="{W}" '
                           f'height="{H:.1f}" preserveAspectRatio="none"{clip_attr}/>')
        for layer in comp.vectors:
            d = _svg_path(view, layer.geojson, False, W, H)
            sw = layer.width_pt * 1000.0 / (slot_mm / 25.4 * 72)   # pt → viewBox units
            dash = (f' stroke-dasharray="{layer.dash[0] * sw:.1f} {layer.dash[1] * sw:.1f}"'
                    if layer.dash else "")
            if d:
                fill = layer.fill or "none"
                els.append(f'<path d="{d}" fill="{fill}" fill-rule="evenodd" '
                           f'stroke="{layer.stroke}" stroke-width="{sw:.2f}"{dash}/>')
            for kind, rings in maps.iter_rings(layer.geojson):
                if kind == "point":
                    fx, fy = view.to_frac(*rings[0][0])
                    r = layer.point_radius_pt * 1000.0 / (slot_mm / 25.4 * 72)
                    els.append(f'<circle cx="{fx * W:.1f}" cy="{fy * H:.1f}" r="{r:.1f}" '
                               f'fill="{layer.fill or layer.stroke}" stroke="{layer.stroke}" '
                               f'stroke-width="{sw:.2f}"/>')
        els.append(f'<rect x="0" y="0" width="{W}" height="{H:.1f}" fill="none" '
                   f'stroke="{style.MUTED}" stroke-width="1"/>')
        if furniture:
            frac, label = maps.scale_bar(view)
            bw = frac * W
            y = H - 18
            els.append(f'<rect x="10" y="{y - 12:.1f}" width="{bw + 70:.1f}" height="26" '
                       f'fill="white" fill-opacity=".8"/>'
                       f'<rect x="16" y="{y:.1f}" width="{bw / 2:.1f}" height="5" fill="black" '
                       f'stroke="black"/><rect x="{16 + bw / 2:.1f}" y="{y:.1f}" '
                       f'width="{bw / 2:.1f}" height="5" fill="white" stroke="black"/>'
                       f'<text x="{22 + bw:.1f}" y="{y + 6:.1f}" font-size="14" '
                       f'font-family="sans-serif">{_e(label)}</text>')
            nx = W - 26
            els.append(f'<circle cx="{nx}" cy="26" r="17" fill="white" fill-opacity=".8"/>'
                       f'<path d="M{nx},10 L{nx - 7},32 L{nx},26 L{nx + 7},32 Z" fill="black"/>'
                       f'<text x="{nx}" y="52" font-size="12" font-weight="bold" '
                       f'text-anchor="middle" font-family="sans-serif">N</text>')
        svg = (f'<svg class="rk-map" viewBox="0 0 {W} {H:.1f}" xmlns="http://www.w3.org/2000/svg" '
               f'role="img" aria-label="{_e(caption)}">{"".join(els)}</svg>')
        legend = ""
        if comp.legend:
            legend = '<div class="rk-legend">' + "".join(
                (f'<span><i class="line" style="border-color:{i.color}"></i>{_e(i.label)}</span>'
                 if i.kind == "line" else
                 f'<span><i style="background:{i.color}"></i>{_e(i.label)}</span>')
                for i in comp.legend) + "</div>"
        attr = f'<div class="rk-attr">{_e(comp.attribution)}</div>' if comp.attribution else ""
        return f"<figure>{svg}{legend}{attr}{self.fig_cap(caption)}</figure>"

    def grid(self, header: List[str], rows: List[List[Any]], align, decimals=None) -> str:
        align = align or ["l"] * len(header)
        decimals = decimals or [None] * len(header)
        head = "".join(f'<th class="{a}">{inline_markup(h)}</th>' for h, a in zip(header, align))
        body = "".join("<tr>" + "".join(
            f'<td class="{a}">{inline_markup(fmt_cell(v, d, self.lang))}</td>'
            for v, a, d in zip(r, align, decimals)) + "</tr>" for r in rows)
        return (f'<div class="rk-scroll"><table><thead><tr>{head}</tr></thead>'
                f"<tbody>{body}</tbody></table></div>")

    def table(self, b: Table) -> str:
        rows = b.rows[: b.max_rows] if b.max_rows else b.rows
        note = b.note
        hidden = len(b.rows) - len(rows)
        if hidden > 0:
            more = t("rows_more", self.lang, n=hidden)
            note = f"{more}. {note}" if note else more
        tail = f'<p class="rk-caption">{inline_markup(note)}</p>' if note else ""
        return self.tab_cap(b.caption) + self.grid(b.columns, rows, b.align, b.decimals) + tail

    def provenance(self, b: ProvenanceTable) -> str:
        lang = self.lang
        head = [t("prov_name", lang), t("prov_dataset", lang), t("prov_bands", lang),
                t("prov_scale", lang), t("prov_reducer", lang), t("prov_computed", lang)]
        rows = []
        for r in b.rows:
            bands = r.get("bands") or []
            bands_txt = ", ".join(map(str, bands[:4])) + (
                f" … (+{len(bands) - 4})" if len(bands) > 4 else "")
            name = str(r.get("name", ""))
            if r.get("degraded"):
                name += f" ({t('prov_degraded', lang)})"
            rows.append([name, r.get("dataset_id", ""), bands_txt,
                         f"{r.get('scale_m')} m" if r.get("scale_m") else "",
                         r.get("reducer", ""), str(r.get("computed_at", ""))[:16].replace("T", " ")])
            rows += [["", f"↳ {n}", "", "", "", ""] for n in (r.get("notes") or [])]
        return self.grid(head, rows, None)

    # ---- page ---------------------------------------------------------------
    def page(self) -> str:
        meta = self.report.meta
        gen = f"{t('generated', meta.lang)} {fmt_datetime_utc(meta.generated_at, meta.lang)}"
        body: List[str] = [
            f'<p class="rk-app">{_e(meta.brand.app_line)}</p>',
            f"<h1>{_e(meta.title)}</h1>",
            f'<p class="rk-subject">{_e(meta.subject)}</p>',
            f'<p class="rk-meta">{_e(gen)} · {_e(meta.app)} {_e(t("version", meta.lang))} '
            f'{_e(meta.app_version)} · <a href="{_e(meta.app_url)}">{_e(meta.app_url)}</a></p>',
        ]
        for section in self.report.sections:
            if section.title:
                anchor = f' id="{_e(section.key)}"' if section.key else ""
                body.append(f"<h2{anchor}>{_e(section.title)}</h2>")
            body += [self.block(b) for b in section.blocks]
        body.append(f"<footer>{_e(meta.brand.app_line)} · "
                    f'<a href="{_e(meta.app_url)}">{_e(meta.app_url)}</a> · {_e(gen)}</footer>')
        css = _CSS % {"accent": self.accent, "ink": style.INK, "muted": style.MUTED,
                      "rule": style.RULE, "zebra": style.ZEBRA,
                      "placeholder": style.PLACEHOLDER_BG}
        head_js = ""
        if self.plotly_needed:
            from plotly.offline import get_plotlyjs
            head_js = f"<script>{get_plotlyjs()}</script>"
        return (f'<!doctype html><html lang="{_e(meta.lang)}"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width, initial-scale=1">'
                f"<title>{_e(meta.title)} — {_e(meta.subject)}</title>"
                f"<style>{css}</style>{head_js}</head><body>{''.join(body)}</body></html>")


def render_html(report: Report) -> bytes:
    """The report as one self-contained HTML file (UTF-8 bytes)."""
    return _Html(report).page().encode("utf-8")
