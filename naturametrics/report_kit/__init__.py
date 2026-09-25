"""report_kit — the shared laid-out report (PDF + HTML) of the umaterra apps.

Canonical copy: /server/naturametrics/naturametrics/report_kit/. Camposcope and
Yvynation carry byte-identical copies made by
``/server/naturametrics/scripts/sync_report_kit.py``; each app's
``tests/test_report_kit_manifest.py`` checks them against ``MANIFEST``.
**Edit the canonical copy only**, then re-sync. Contract: doc/14-pdf-report.md §2.

Rules for code in this package: relative imports only; never import the host
app or reflex; ``ee`` only lazily inside ``maps``; Python 3.11 compatible.
"""

from __future__ import annotations

from .model import (Block, Brand, Callout, Citation, ContentsItem, ContentsList,
                    Figure, KeyValues, LegendItem, LocatorMap, MapComposition,
                    MapFigure, PageBreak, Paragraph, ProvenanceTable, Report,
                    ReportMeta, Section, SideBySide, Table, VectorLayer)

KIT_VERSION = "0.1.2"


def render_pdf(report: Report) -> bytes:
    """PDF bytes (reportlab is imported on first use)."""
    from .pdf import render_pdf as _render
    return _render(report)


def render_html(report: Report) -> bytes:
    """One self-contained HTML file, UTF-8 bytes."""
    from .html import render_html as _render
    return _render(report)


__all__ = [
    "KIT_VERSION", "render_pdf", "render_html",
    "Block", "Brand", "Callout", "Citation", "ContentsItem", "ContentsList",
    "Figure", "KeyValues", "LegendItem", "LocatorMap", "MapComposition", "MapFigure",
    "PageBreak", "Paragraph", "ProvenanceTable", "Report", "ReportMeta", "Section",
    "SideBySide", "Table", "VectorLayer",
]
