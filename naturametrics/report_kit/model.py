"""The report content model — what a report *is*, independent of how it is drawn.

Each app builds a :class:`Report` from its own state (doc/14 §2.3); the kit's
two renderers (``pdf.render_pdf``, ``html.render_html``) draw it. Plain
dataclasses only: no Reflex, Earth Engine or pandas objects live in a model,
so a model can be built, inspected and tested without any of them.

One model, two renderers, is decision R4: the PDF and the HTML report can not
drift apart because there is only one description of what they contain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Literal, Optional, Sequence, Tuple, Union

Slot = Literal["full", "half"]
ContentsStatus = Literal["included", "not_run", "unavailable", "excluded"]
CalloutKind = Literal["disclosure", "note", "warning"]


@dataclass
class Brand:
    """Per-app identity: the accent colour and the line printed in the page
    header/footer ("umaterra · Camposcope")."""

    accent: str = "#2f7d4f"
    app_line: str = "umaterra"


@dataclass
class ReportMeta:
    app: str
    app_url: str
    app_version: str
    title: str
    subject: str
    lang: str = "pt"
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc))
    brand: Brand = field(default_factory=Brand)


# --------------------------------------------------------------------------- #
# Blocks
# --------------------------------------------------------------------------- #

@dataclass
class Paragraph:
    """Body text. ``**bold**`` and ``*italic*`` are the only markup; every
    other character is escaped by the renderers."""

    text: str
    lead: bool = False


@dataclass
class KeyValues:
    rows: List[Tuple[str, str]]
    caption: str = ""


@dataclass
class Figure:
    """A chart. The HTML renderer uses ``fig_json`` (interactive Plotly), the
    PDF renderer ``png``. With neither, both draw a "figure unavailable"
    placeholder carrying ``unavailable_reason`` — a missing chart is stated,
    never silently dropped."""

    key: str
    caption: str
    slot: Slot = "full"
    aspect: float = 0.56
    fig_json: Optional[dict] = None
    png: Optional[bytes] = None
    unavailable_reason: str = ""


@dataclass
class VectorLayer:
    """GeoJSON drawn as vector paths over a map (outlines, rings, points).
    ``width_pt`` in points; ``dash`` a reportlab/SVG dash pattern."""

    geojson: dict
    stroke: str = "#111111"
    width_pt: float = 1.2
    dash: Optional[Tuple[float, float]] = None
    fill: Optional[str] = None
    label: str = ""
    point_radius_pt: float = 2.5


@dataclass
class LegendItem:
    color: str
    label: str
    kind: Literal["fill", "line"] = "fill"


@dataclass
class MapComposition:
    """Everything one map shows: the view (``maps.MapView``), raster layers
    as encoded bytes (a JPEG backdrop, PNG overlays bottom-to-top), vector
    layers, an optional clip shape for the overlays, the legend and the
    attribution line."""

    view: Any                                   # maps.MapView
    backdrop: Optional[bytes] = None
    overlays: List[bytes] = field(default_factory=list)
    vectors: List[VectorLayer] = field(default_factory=list)
    clip_to: Optional[dict] = None
    legend: List[LegendItem] = field(default_factory=list)
    attribution: str = ""


@dataclass
class MapFigure:
    composition: MapComposition
    caption: str
    slot: Slot = "full"


@dataclass
class LocatorMap:
    """Brazil's states with the object marked — drawn from the kit's own
    boundary file, no network."""

    geometry: dict
    label: str = ""
    slot: Slot = "half"
    highlight_ufs: Sequence[str] = ()


@dataclass
class Table:
    columns: List[str]
    rows: List[List[Any]]
    caption: str
    align: Optional[List[str]] = None          # "l" / "r" per column
    max_rows: int = 40
    note: str = ""
    #: Decimals per column for numeric cells (None → 1 for floats, 0 for
    #: ints). Numbers are formatted by the renderer in the report's locale;
    #: pass strings for anything already formatted.
    decimals: Optional[List[Optional[int]]] = None

    @classmethod
    def from_frame(cls, df, headers: dict, caption: str, **kw) -> "Table":
        """From a pandas DataFrame, keeping ``headers``' key order and
        labels. pandas is only touched here, and only through ``df``."""
        cols = [c for c in headers if c in df.columns]
        rows = df[cols].values.tolist() if cols else []
        align = kw.pop("align", None)
        if align is None:
            align = ["r" if str(df[c].dtype).startswith(("int", "float")) else "l"
                     for c in cols]
        return cls(columns=[headers[c] for c in cols], rows=rows,
                   caption=caption, align=align, **kw)


@dataclass
class Callout:
    text: str
    kind: CalloutKind = "note"
    title: str = ""


@dataclass
class ContentsItem:
    title: str
    status: ContentsStatus = "included"
    reason: str = ""


@dataclass
class ContentsList:
    items: List[ContentsItem]


@dataclass
class ProvenanceTable:
    """Rows are each app's ``Provenance.to_dict()`` (or a dict with the same
    keys: name, dataset_id, bands, scale_m, reducer, degraded, computed_at,
    notes)."""

    rows: List[dict]


@dataclass
class Citation:
    text: str
    sources: List[str] = field(default_factory=list)
    attributions: List[str] = field(default_factory=list)


@dataclass
class SideBySide:
    left: "Block"
    right: "Block"


@dataclass
class PageBreak:
    pass


Block = Union[Paragraph, KeyValues, Figure, MapFigure, LocatorMap, Table,
              Callout, ContentsList, ProvenanceTable, Citation, SideBySide,
              PageBreak]


@dataclass
class Section:
    title: str
    blocks: List[Block] = field(default_factory=list)
    key: str = ""


@dataclass
class Report:
    meta: ReportMeta
    sections: List[Section] = field(default_factory=list)

    def blocks(self):
        """Every block in order, SideBySide children included — for tests and
        guards that scan a report's content (e.g. Camposcope's C4 scan)."""
        for section in self.sections:
            for block in section.blocks:
                if isinstance(block, SideBySide):
                    yield block.left
                    yield block.right
                else:
                    yield block
