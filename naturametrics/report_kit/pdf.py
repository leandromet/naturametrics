"""PDF renderer (reportlab) — doc/14 §2.4.

``render_pdf(report) -> bytes``. A4 portrait, Noto Sans, one flowable per
model block. Maps are drawn by :class:`MapFlowable`: raster layers as images,
outlines/rings/points as vector paths, then the frame furniture (scale bar,
north arrow); the legend and attribution sit below the map, never on it.

reportlab documents are independent, so rendering is thread-safe once the
fonts are registered — which happens once, at import.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, List, Optional, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Flowable, Frame,
                                Image, KeepTogether, LongTable, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

from . import images, locator, maps, style
from .model import (Callout, Citation, ContentsList, Figure, KeyValues, LocatorMap,
                    MapComposition, MapFigure, PageBreak as PageBreakBlock,
                    Paragraph as ParagraphBlock, ProvenanceTable, Report,
                    SideBySide, Table as TableBlock)
from .text import fmt_cell, fmt_datetime_utc, inline_markup, t

_FONT_DIR = Path(__file__).resolve().parent / "fonts"


def _register_fonts() -> None:
    if style.FONT_REGULAR in pdfmetrics.getRegisteredFontNames():
        return
    pdfmetrics.registerFont(TTFont(style.FONT_REGULAR, str(_FONT_DIR / "NotoSans-Regular.ttf")))
    pdfmetrics.registerFont(TTFont(style.FONT_BOLD, str(_FONT_DIR / "NotoSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont(style.FONT_ITALIC, str(_FONT_DIR / "NotoSans-Italic.ttf")))
    pdfmetrics.registerFont(TTFont(style.FONT_SYMBOLS, str(_FONT_DIR / "NotoSansMath-Subset.ttf")))
    pdfmetrics.registerFontFamily(style.FONT_REGULAR, normal=style.FONT_REGULAR,
                                  bold=style.FONT_BOLD, italic=style.FONT_ITALIC,
                                  boldItalic=style.FONT_BOLD)


_register_fonts()

# Codepoints each font can draw. reportlab silently DROPS a character its font
# lacks — the system Noto Sans has no − → ≥ ≤ ↳, so "−3,2" printed as "3,2" and
# "2008→2024" as "20082024". Any such character is drawn with the symbol subset
# instead (Paragraph markup), or replaced by an ASCII stand-in on the canvas.
_MAIN_CMAP = frozenset(pdfmetrics.getFont(style.FONT_REGULAR).face.charToGlyph)
_SYMBOL_CMAP = frozenset(pdfmetrics.getFont(style.FONT_SYMBOLS).face.charToGlyph)
_CANVAS_ASCII = {"\u2212": "-", "\u2192": "->", "\u2190": "<-", "\u2265": ">=",
                 "\u2264": "<=", "\u21b3": "-", "\u2248": "~"}


def _glyph_fallback(markup: str) -> str:
    """Wrap every character Noto Sans cannot draw in the symbol font. Safe on
    kit markup: tags and entities are ASCII, which the main font covers."""
    out = []
    for ch in markup:
        cp = ord(ch)
        if cp > 127 and cp not in _MAIN_CMAP and cp in _SYMBOL_CMAP:
            out.append(f'<font name="{style.FONT_SYMBOLS}">{ch}</font>')
        else:
            out.append(ch)
    return "".join(out)


def _canvas_text(text: str) -> str:
    """Canvas strings (header/footer, map labels) take one font only, so
    missing glyphs get ASCII stand-ins rather than disappearing."""
    return "".join(_CANVAS_ASCII.get(ch, ch) if ord(ch) not in _MAIN_CMAP else ch
                   for ch in text)

# --------------------------------------------------------------------------- #
# Styles
# --------------------------------------------------------------------------- #


def _styles(accent: str) -> dict:
    ink, muted = colors.HexColor(style.INK), colors.HexColor(style.MUTED)
    base = dict(fontName=style.FONT_REGULAR, textColor=ink, alignment=TA_LEFT)
    return {
        "body": ParagraphStyle("body", fontSize=style.BODY_PT,
                               leading=style.BODY_LEADING, spaceAfter=5, **base),
        "lead": ParagraphStyle("lead", fontSize=style.BODY_PT + 1,
                               leading=style.BODY_LEADING + 1.5, spaceAfter=6, **base),
        "h1": ParagraphStyle("h1", fontName=style.FONT_BOLD, fontSize=style.H1_PT,
                             leading=style.H1_PT * 1.25, textColor=ink, spaceAfter=2),
        "subject": ParagraphStyle("subject", fontName=style.FONT_REGULAR,
                                  fontSize=style.H2_PT, leading=style.H2_PT * 1.3,
                                  textColor=colors.HexColor(accent), spaceAfter=3),
        "meta": ParagraphStyle("meta", fontName=style.FONT_REGULAR,
                               fontSize=style.CAPTION_PT, leading=style.CAPTION_PT * 1.35,
                               textColor=muted, spaceAfter=8),
        "h2": ParagraphStyle("h2", fontName=style.FONT_BOLD, fontSize=style.H2_PT,
                             leading=style.H2_PT * 1.3, textColor=ink,
                             spaceBefore=10, spaceAfter=5),
        "caption": ParagraphStyle("caption", fontName=style.FONT_REGULAR,
                                  fontSize=style.CAPTION_PT, leading=style.CAPTION_PT * 1.35,
                                  textColor=muted, spaceBefore=3, spaceAfter=8),
        "cell": ParagraphStyle("cell", fontName=style.FONT_REGULAR, fontSize=style.TABLE_PT,
                               leading=style.TABLE_PT * 1.3, textColor=ink),
        "cell_r": ParagraphStyle("cell_r", fontName=style.FONT_REGULAR,
                                 fontSize=style.TABLE_PT, leading=style.TABLE_PT * 1.3,
                                 textColor=ink, alignment=2),
        "cell_head": ParagraphStyle("cell_head", fontName=style.FONT_BOLD,
                                    fontSize=style.TABLE_PT, leading=style.TABLE_PT * 1.3,
                                    textColor=ink),
        "cell_head_r": ParagraphStyle("cell_head_r", fontName=style.FONT_BOLD,
                                      fontSize=style.TABLE_PT, leading=style.TABLE_PT * 1.3,
                                      textColor=ink, alignment=2),
        "key": ParagraphStyle("key", fontName=style.FONT_BOLD, fontSize=style.TABLE_PT + 0.5,
                              leading=(style.TABLE_PT + 0.5) * 1.3, textColor=muted),
        "value": ParagraphStyle("value", fontName=style.FONT_REGULAR,
                                fontSize=style.TABLE_PT + 0.5,
                                leading=(style.TABLE_PT + 0.5) * 1.3, textColor=ink),
        "small": ParagraphStyle("small", fontName=style.FONT_REGULAR, fontSize=style.SMALL_PT,
                                leading=style.SMALL_PT * 1.3, textColor=muted),
        "placeholder": ParagraphStyle("placeholder", fontName=style.FONT_ITALIC,
                                      fontSize=style.BODY_PT, leading=style.BODY_LEADING,
                                      textColor=muted, alignment=1),
    }


def _p(text: str, st: ParagraphStyle) -> Paragraph:
    return Paragraph(_glyph_fallback(inline_markup(text)), st)


# --------------------------------------------------------------------------- #
# Maps
# --------------------------------------------------------------------------- #


class MapFlowable(Flowable):
    """One ``MapComposition`` drawn ``width_pt`` wide, height from the view's
    aspect. ``furniture`` adds the scale bar and north arrow (off for the
    locator, whose projection makes a single scale meaningless)."""

    def __init__(self, comp: MapComposition, width_pt: float, furniture: bool = True):
        super().__init__()
        self.comp = comp
        self.width = width_pt
        self.height = width_pt * comp.view.aspect
        self.furniture = furniture

    def wrap(self, avail_w, avail_h):
        return self.width, self.height

    def _xy(self, lon: float, lat: float):
        fx, fy = self.comp.view.to_frac(lon, lat)
        return fx * self.width, self.height - fy * self.height

    def _path(self, c, geojson, polygons_only: bool = False):
        path = c.beginPath()
        empty = True
        for kind, parts in maps.iter_rings(geojson):
            if kind == "point" or (polygons_only and kind != "polygon"):
                continue
            for part in parts:
                if len(part) < 2:
                    continue
                x, y = self._xy(*part[0])
                path.moveTo(x, y)
                for lon, lat in part[1:]:
                    path.lineTo(*self._xy(lon, lat))
                if kind == "polygon":
                    path.close()
                empty = False
        return None if empty else path

    def draw(self):
        c, comp, w, h = self.canv, self.comp, self.width, self.height
        c.saveState()
        frame = c.beginPath()
        frame.rect(0, 0, w, h)
        c.clipPath(frame, stroke=0, fill=0)
        if comp.backdrop:
            c.drawImage(ImageReader(io.BytesIO(comp.backdrop)), 0, 0, w, h)
        if comp.overlays:
            c.saveState()
            if comp.clip_to:
                clip = self._path(c, comp.clip_to, polygons_only=True)
                if clip is not None:
                    c.clipPath(clip, stroke=0, fill=0, fillMode=0)   # even-odd: holes stay out
            for ov in comp.overlays:
                c.drawImage(ImageReader(io.BytesIO(ov)), 0, 0, w, h, mask="auto")
            c.restoreState()
        for layer in comp.vectors:
            c.setStrokeColor(colors.HexColor(layer.stroke))
            c.setLineWidth(layer.width_pt)
            if layer.dash:
                c.setDash(list(layer.dash), 0)
            else:
                c.setDash()
            if layer.fill:
                c.setFillColor(colors.HexColor(layer.fill))
            path = self._path(c, layer.geojson)
            if path is not None:
                c.drawPath(path, stroke=1, fill=1 if layer.fill else 0)
            for kind, parts in maps.iter_rings(layer.geojson):
                if kind == "point":
                    x, y = self._xy(*parts[0][0])
                    c.setDash()
                    c.setFillColor(colors.HexColor(layer.fill or layer.stroke))
                    c.circle(x, y, layer.point_radius_pt, stroke=1, fill=1)
        c.restoreState()
        c.setDash()
        c.setStrokeColor(colors.HexColor(style.MUTED))
        c.setLineWidth(0.5)
        c.rect(0, 0, w, h, stroke=1, fill=0)
        if self.furniture:
            self._scale_bar(c)
            self._north(c)

    def _scale_bar(self, c):
        frac, label = maps.scale_bar(self.comp.view)
        bar_w = frac * self.width
        x, y = 8, 8
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.8))
        c.setStrokeColor(colors.Color(1, 1, 1, alpha=0))
        c.rect(x - 4, y - 4, bar_w + 8 + 40, 14, stroke=0, fill=1)
        half = bar_w / 2
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.5)
        c.setFillColor(colors.black)
        c.rect(x, y, half, 3, stroke=1, fill=1)
        c.setFillColor(colors.white)
        c.rect(x + half, y, half, 3, stroke=1, fill=1)
        c.setFillColor(colors.black)
        c.setFont(style.FONT_REGULAR, 6.5)
        c.drawString(x + bar_w + 4, y, _canvas_text(label))

    def _north(self, c):
        x, y = self.width - 14, self.height - 22
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.8))
        c.circle(x, y + 5, 9, stroke=0, fill=1)
        c.setFillColor(colors.black)
        path = c.beginPath()
        path.moveTo(x, y + 12)
        path.lineTo(x - 4, y + 1)
        path.lineTo(x, y + 4)
        path.lineTo(x + 4, y + 1)
        path.close()
        c.drawPath(path, stroke=0, fill=1)
        c.setFont(style.FONT_BOLD, 6)
        c.drawCentredString(x, y - 5, "N")


class _Swatch(Flowable):
    def __init__(self, color: str, kind: str):
        super().__init__()
        self.color, self.kind = color, kind
        self.width, self.height = 10, 7

    def draw(self):
        c = self.canv
        if self.kind == "line":
            c.setStrokeColor(colors.HexColor(self.color))
            c.setLineWidth(1.6)
            c.line(0, 3.5, 10, 3.5)
        else:
            c.setFillColor(colors.HexColor(self.color))
            c.setStrokeColor(colors.HexColor(style.RULE))
            c.setLineWidth(0.3)
            c.rect(0, 0, 10, 7, stroke=1, fill=1)


def _legend(comp: MapComposition, width_pt: float, st: dict) -> List[Flowable]:
    out: List[Flowable] = []
    if comp.legend:
        per_row = max(1, int(width_pt // 150))
        cells = []
        for item in comp.legend:
            cells += [_Swatch(item.color, item.kind), _p(item.label, st["small"])]
        rows = [cells[i:i + 2 * per_row] for i in range(0, len(cells), 2 * per_row)]
        rows[-1] += [""] * (2 * per_row - len(rows[-1]))
        col_w = width_pt / per_row
        tbl = Table(rows, colWidths=[12, col_w - 12] * per_row)
        tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 1),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                                 ("TOPPADDING", (0, 0), (-1, -1), 1),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        tbl.hAlign = "LEFT"
        out.append(Spacer(1, 3))
        out.append(tbl)
    if comp.attribution:
        out.append(_p(comp.attribution, st["small"]))
    return out


# --------------------------------------------------------------------------- #
# Blocks → flowables
# --------------------------------------------------------------------------- #


def _unwrap(flowables: List[Flowable]) -> List[Flowable]:
    out: List[Flowable] = []
    for f in flowables:
        if isinstance(f, KeepTogether):
            out += _unwrap(list(f._content))
        elif isinstance(f, CondPageBreak):
            continue
        else:
            out.append(f)
    return out


class _Renderer:
    def __init__(self, report: Report):
        self.report = report
        self.lang = report.meta.lang
        self.accent = report.meta.brand.accent
        self.st = _styles(self.accent)
        self.n_fig = 0
        self.n_tab = 0

    # ---- captions --------------------------------------------------------
    def _fig_caption(self, caption: str) -> Paragraph:
        self.n_fig += 1
        return _p(f"**{t('figure', self.lang)} {self.n_fig}** — {caption}",
                  self.st["caption"])

    def _tab_caption(self, caption: str) -> Paragraph:
        self.n_tab += 1
        st = ParagraphStyle("tabcap", parent=self.st["caption"], spaceBefore=6, spaceAfter=3)
        return _p(f"**{t('table', self.lang)} {self.n_tab}** — {caption}", st)

    # ---- blocks -------------------------------------------------------------
    def block(self, b: Any, width_pt: float) -> List[Flowable]:
        handler = {
            ParagraphBlock: self._paragraph, KeyValues: self._keyvalues,
            Figure: self._figure, MapFigure: self._mapfigure,
            LocatorMap: self._locator, TableBlock: self._table,
            Callout: self._callout, ContentsList: self._contents,
            ProvenanceTable: self._provenance, Citation: self._citation,
            SideBySide: self._side_by_side,
        }.get(type(b))
        if isinstance(b, PageBreakBlock):
            return [PageBreak()]
        if handler is None:
            raise TypeError(f"unknown report block {type(b).__name__}")
        return handler(b, width_pt)

    def _paragraph(self, b: ParagraphBlock, width_pt):
        return [_p(b.text, self.st["lead" if b.lead else "body"])]

    def _keyvalues(self, b: KeyValues, width_pt):
        rows = [[_p(k, self.st["key"]), _p(v, self.st["value"])] for k, v in b.rows]
        if not rows:
            return []
        tbl = Table(rows, colWidths=[width_pt * 0.36, width_pt * 0.64])
        tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor(style.RULE)),
            ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        out: List[Flowable] = [tbl]
        if b.caption:
            out.append(_p(b.caption, self.st["caption"]))
        return out

    def _figure(self, b: Figure, width_pt):
        slot_pt = min(width_pt, style.SLOT_MM[b.slot] * mm)
        if b.png:
            data = images.fit_image(b.png, slot_pt / mm, "flat")
            _, pw, ph = images.image_size(data)
            img = Image(io.BytesIO(data), width=slot_pt, height=slot_pt * ph / pw)
            img.hAlign = "LEFT"
            return [KeepTogether([img, self._fig_caption(b.caption)])]
        text = t("figure_unavailable", self.lang)
        if b.unavailable_reason:
            text += f" — {b.unavailable_reason}"
        box = Table([[_p(text, self.st["placeholder"])]], colWidths=[slot_pt],
                    rowHeights=[max(40, slot_pt * b.aspect * 0.5)])
        box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1),
                                  colors.HexColor(style.PLACEHOLDER_BG)),
                                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        box.hAlign = "LEFT"
        return [KeepTogether([box, self._fig_caption(b.caption)])]

    def _map_flowables(self, comp: MapComposition, caption: str, width_pt: float,
                       furniture: bool = True) -> List[Flowable]:
        slot_mm = width_pt / mm
        fitted = MapComposition(
            view=comp.view,
            backdrop=images.fit_image(comp.backdrop, slot_mm, "photo") if comp.backdrop else None,
            overlays=[images.fit_image(o, slot_mm, "flat") for o in comp.overlays],
            vectors=comp.vectors, clip_to=comp.clip_to, legend=comp.legend,
            attribution=comp.attribution)
        parts: List[Flowable] = [MapFlowable(fitted, width_pt, furniture)]
        parts += _legend(fitted, width_pt, self.st)
        parts.append(self._fig_caption(caption))
        return [KeepTogether(parts)]

    def _mapfigure(self, b: MapFigure, width_pt):
        return self._map_flowables(b.composition, b.caption,
                                   min(width_pt, style.SLOT_MM[b.slot] * mm))

    def _locator(self, b: LocatorMap, width_pt):
        comp = locator.compose(b, self.accent)
        return self._map_flowables(comp, b.label or "", min(width_pt, style.SLOT_MM[b.slot] * mm),
                                   furniture=False)

    def _grid(self, header: List[str], body: List[List[Any]], align: Optional[List[str]],
              width_pt: float, caption: Optional[str], note: str = "",
              decimals: Optional[List[Optional[int]]] = None,
              nowrap: Sequence[int] = ()) -> List[Flowable]:
        n = len(header)
        align = align or ["l"] * n
        decimals = decimals or [None] * n
        text = [[fmt_cell(v, decimals[i] if i < len(decimals) else None, self.lang)
                 for i, v in enumerate(row[:n])] for row in body]
        data = [[_p(h, self.st["cell_head_r" if align[i] == "r" else "cell_head"])
                 for i, h in enumerate(header)]]
        data += [[_p(v, self.st["cell_r" if align[i] == "r" else "cell"])
                  for i, v in enumerate(row)] for row in text]
        # Widths proportional to content, with a floor at the header's longest
        # word so a narrow numeric column never breaks its own title.
        lens = []
        for i in range(n):
            content = max([len(r[i]) for r in text[:60] if i < len(r)] or [0])
            word = max((len(w) for w in str(header[i]).split()), default=4)
            lens.append(min(max(content, word + 1, 5), 40))
        total = float(sum(lens)) or 1.0
        widths = [width_pt * x / total for x in lens]
        # Absolute floor: a column is never narrower than its header's longest
        # word at the table font (≈ 0.55 em per character) plus padding.
        floors = [min(width_pt / n, 0.55 * style.TABLE_PT * max(
            (len(w) for w in str(header[i]).split()), default=4) + 8) for i in range(n)]
        for i in nowrap:   # e.g. timestamps: the floor is the whole content
            longest = max([len(r[i]) for r in text if i < len(r)] or [0])
            floors[i] = max(floors[i], min(width_pt / 2, 0.55 * style.TABLE_PT * longest + 8))
        for _ in range(3):
            short = [i for i in range(n) if widths[i] < floors[i]]
            if not short:
                break
            deficit = sum(floors[i] - widths[i] for i in short)
            for i in short:
                widths[i] = floors[i]
            rest = [i for i in range(n) if i not in short]
            pool = sum(widths[i] for i in rest) or 1.0
            for i in rest:
                widths[i] -= deficit * widths[i] / pool
        tbl = LongTable(data, colWidths=widths, repeatRows=1)
        cmds = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(style.INK)),
            ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor(style.RULE)),
            ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        for r in range(2, len(data), 2):
            cmds.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor(style.ZEBRA)))
        tbl.setStyle(TableStyle(cmds))
        tbl.hAlign = "LEFT"
        out: List[Flowable] = []
        if caption is not None:
            out.append(CondPageBreak(40 * mm))
            out.append(self._tab_caption(caption))
        out.append(tbl)
        out.append(_p(note, self.st["caption"]) if note else Spacer(1, 7))
        return out

    def _table(self, b: TableBlock, width_pt):
        rows = b.rows[: b.max_rows] if b.max_rows else b.rows
        note = b.note
        hidden = len(b.rows) - len(rows)
        if hidden > 0:
            more = t("rows_more", self.lang, n=hidden)
            note = f"{more}. {note}" if note else more
        return self._grid(b.columns, rows, b.align, width_pt, b.caption, note, b.decimals)

    def _callout(self, b: Callout, width_pt):
        border, bg = style.CALLOUT_COLORS.get(b.kind, style.CALLOUT_COLORS["note"])
        text = f"**{b.title}** — {b.text}" if b.title else b.text
        st = self.st["body"] if b.kind != "disclosure" else ParagraphStyle(
            "disc", parent=self.st["body"], fontName=style.FONT_BOLD)
        box = Table([[_p(text, st)]], colWidths=[width_pt])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
            ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(border)),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return [box, Spacer(1, 6)]

    def _contents(self, b: ContentsList, width_pt):
        body = [[i.title, t(f"status_{i.status}", self.lang), i.reason] for i in b.items]
        header = {"pt": ["Seção", "Situação", "Observação"],
                  "es": ["Sección", "Estado", "Observación"],
                  "fr": ["Section", "Statut", "Remarque"]}.get(
                      self.lang, ["Section", "Status", "Note"])
        return self._grid(header, body, ["l", "l", "l"], width_pt, None)

    def _provenance(self, b: ProvenanceTable, width_pt):
        lang = self.lang
        header = [t("prov_name", lang), t("prov_dataset", lang), t("prov_bands", lang),
                  t("prov_scale", lang), t("prov_reducer", lang), t("prov_computed", lang)]
        body = []
        for r in b.rows:
            bands = r.get("bands") or []
            bands_txt = (", ".join(map(str, bands[:4])) + (f" … (+{len(bands) - 4})"
                                                           if len(bands) > 4 else ""))
            name = str(r.get("name", ""))
            if r.get("degraded"):
                name += f" ({t('prov_degraded', lang)})"
            computed = str(r.get("computed_at", ""))[:16].replace("T", "\u00a0")
            body.append([name, r.get("dataset_id", ""), bands_txt,
                         f"{r.get('scale_m', '')} m" if r.get("scale_m") else "",
                         r.get("reducer", ""), computed])
            for note in r.get("notes") or []:
                body.append(["", f"↳ {note}", "", "", "", ""])
        return self._grid(header, body, None, width_pt, None, nowrap=(5,))

    def _citation(self, b: Citation, width_pt):
        out: List[Flowable] = [_p(f"**{t('how_to_cite', self.lang)}.** {b.text}",
                                  self.st["body"])]
        if b.sources:
            out.append(_p(f"**{t('sources', self.lang)}**", self.st["body"]))
            out += [_p(f"• {s}", self.st["small"]) for s in b.sources]
        if b.attributions:
            out.append(Spacer(1, 4))
            out.append(_p(f"**{t('attributions', self.lang)}**", self.st["body"]))
            out += [_p(f"• {a}", self.st["small"]) for a in b.attributions]
        return out

    def _side_by_side(self, b: SideBySide, width_pt):
        half = (width_pt - style.GUTTER_MM * mm) / 2
        # KeepTogether reports an unbounded height inside a table cell, so
        # cell content is unwrapped; the row itself never splits anyway.
        left = _unwrap(self.block(b.left, half))
        right = _unwrap(self.block(b.right, half))
        tbl = Table([[left, right]], colWidths=[half + style.GUTTER_MM * mm, half])
        tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (0, -1), style.GUTTER_MM * mm),
                                 ("RIGHTPADDING", (1, 0), (1, -1), 0),
                                 ("TOPPADDING", (0, 0), (-1, -1), 0),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        tbl.hAlign = "LEFT"
        return [tbl]

    # ---- document -----------------------------------------------------------
    def story(self) -> List[Flowable]:
        meta = self.report.meta
        width = style.TEXT_W_MM * mm
        gen = f"{t('generated', meta.lang)} {fmt_datetime_utc(meta.generated_at, meta.lang)}"
        out: List[Flowable] = [
            _p(meta.brand.app_line, ParagraphStyle(
                "app", parent=self.st["meta"], textColor=colors.HexColor(self.accent),
                fontName=style.FONT_BOLD, spaceAfter=2)),
            _p(meta.title, self.st["h1"]),
            _p(meta.subject, self.st["subject"]),
            _p(f"{gen} · {meta.app} {t('version', meta.lang)} {meta.app_version} · "
               f"{meta.app_url}", self.st["meta"]),
        ]
        for section in self.report.sections:
            flows: List[Flowable] = []
            for block in section.blocks:
                flows += self.block(block, width)
            if section.title:
                heading = _p(section.title, self.st["h2"])
                # A heading never ends a page alone: it travels with the first
                # block — unless that is a table, which may split, so it only
                # asks for room for its first rows.
                first = next((i for i, f in enumerate(flows)
                              if not isinstance(f, (Spacer, CondPageBreak))), None)
                starts_with_table = first is not None and (
                    isinstance(flows[first], LongTable)
                    or (first + 1 < len(flows) and isinstance(flows[first + 1], LongTable)))
                if first is None or starts_with_table:
                    out += [CondPageBreak(60 * mm), heading] + flows
                else:
                    # The heading keeps its intro paragraphs AND the first
                    # figure/map after them — a heading plus intro alone at the
                    # foot of a page, chart overleaf, is what this prevents.
                    last = first
                    while (last + 1 < len(flows) and isinstance(flows[last], Paragraph)
                           and not isinstance(flows[last + 1], (LongTable, CondPageBreak))):
                        last += 1
                    out.append(KeepTogether([heading] + flows[:last + 1]))
                    out += flows[last + 1:]
            else:
                out += flows
        return out


def _canvas_class(meta):
    """A canvas that defers page decoration until the page count is known —
    so the footer can say "page n of total"."""
    accent = colors.HexColor(meta.brand.accent)
    lang = meta.lang
    gen = fmt_datetime_utc(meta.generated_at, lang)

    class _NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("initialFontName", style.FONT_REGULAR)
            super().__init__(*args, **kwargs)
            self._pages: List[dict] = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                self._decorate(total)
                super().showPage()
            super().save()

        def _decorate(self, total: int):
            page_w, page_h = A4
            n = self._pageNumber
            self.saveState()
            x0, x1 = style.MARGIN_X_MM * mm, page_w - style.MARGIN_X_MM * mm
            if n > 1:
                y = page_h - style.MARGIN_TOP_MM * mm + 4
                self.setFont(style.FONT_BOLD, 7.5)
                self.setFillColor(accent)
                self.drawString(x0, y, _canvas_text(meta.brand.app_line))
                self.setFont(style.FONT_REGULAR, 7.5)
                self.setFillColor(colors.HexColor(style.MUTED))
                subject = meta.subject if len(meta.subject) < 90 else meta.subject[:87] + "…"
                self.drawRightString(x1, y, _canvas_text(subject))
                self.setStrokeColor(colors.HexColor(style.RULE))
                self.setLineWidth(0.4)
                self.line(x0, y - 3, x1, y - 3)
            y = style.MARGIN_BOTTOM_MM * mm - 9
            self.setStrokeColor(colors.HexColor(style.RULE))
            self.setLineWidth(0.4)
            self.line(x0, y + 8, x1, y + 8)
            self.setFont(style.FONT_REGULAR, 7)
            self.setFillColor(colors.HexColor(style.MUTED))
            self.drawString(x0, y, _canvas_text(f"{meta.brand.app_line} · {meta.app_url}"))
            self.drawRightString(x1, y, _canvas_text(
                f"{t('page_of', lang, n=n, total=total)} — {t('generated', lang)} {gen}"))
            self.restoreState()

    return _NumberedCanvas


def render_pdf(report: Report) -> bytes:
    """The report as PDF bytes."""
    buf = io.BytesIO()
    page_w, page_h = A4
    frame = Frame(style.MARGIN_X_MM * mm, style.MARGIN_BOTTOM_MM * mm,
                  style.TEXT_W_MM * mm,
                  page_h - (style.MARGIN_TOP_MM + style.MARGIN_BOTTOM_MM) * mm,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc = BaseDocTemplate(
        buf, pagesize=A4, title=report.meta.title, author=report.meta.brand.app_line,
        subject=report.meta.subject, creator=f"{report.meta.app} {report.meta.app_version}",
        pageTemplates=[PageTemplate(id="page", frames=[frame])])
    doc.build(_Renderer(report).story(), canvasmaker=_canvas_class(report.meta))
    return buf.getvalue()
