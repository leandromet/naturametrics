"""A streaming ODS writer.

**Why not odfpy.** The obvious choice — ``pandas.to_excel(engine="odf")`` — builds
the whole spreadsheet as an in-memory DOM, and it degrades superlinearly:
measured 1.3 s for 5 000 rows, 7 s for 20 000, **42 s for 60 000**. A buffer
export covering a few hundred conglomerados is several hundred thousand rows, so
odfpy would turn a 30-second Earth Engine job into a quarter-hour of XML
building, holding all of it in RAM.

An ODS file is a ZIP holding a handful of XML parts, and a table of plain values
is a trivial subset of the schema. Writing ``content.xml`` straight into the
archive as a stream is linear, needs no intermediate structure, and lets the
export stay a single file the user can double-click — which is the whole point of
choosing ODS over a folder of CSVs.

Deliberately not supported: styling, formulas, merged cells, dates as dates. Every
value is a string or a number. If this ever needs more, that is the moment to
reach for a real library, not to grow this one.
"""

from __future__ import annotations

import io
import logging
import zipfile
from typing import Any, Iterable, Iterator, Sequence
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)

MIMETYPE = "application/vnd.oasis.opendocument.spreadsheet"

_NS = (
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'office:version="1.2"'
)

_MANIFEST = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<manifest:manifest '
    'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
    'manifest:version="1.2">'
    f'<manifest:file-entry manifest:full-path="/" manifest:media-type="{MIMETYPE}"/>'
    '<manifest:file-entry manifest:full-path="content.xml" '
    'manifest:media-type="text/xml"/>'
    '</manifest:manifest>'
)

#: LibreOffice and Excel both stop at 2^20 rows. A sheet past it does not fail
#: loudly — it silently loses the tail, which is the worst possible outcome for
#: an export, so it is refused here instead.
MAX_ROWS_PER_SHEET = 1_048_576


class SheetTooLarge(ValueError):
    """A sheet exceeded what a spreadsheet application can open."""


def _cell(value: Any) -> str:
    if value is None or value == "":
        return "<table:table-cell/>"
    if isinstance(value, bool):
        # Before the numeric branch: bool is a subclass of int, and a boolean
        # written as 1/0 loses its meaning in a metadata sheet.
        text = "sim" if value else "não"
        return (f'<table:table-cell office:value-type="string">'
                f'<text:p>{text}</text:p></table:table-cell>')
    if isinstance(value, (int, float)):
        if value != value or value in (float("inf"), float("-inf")):
            return "<table:table-cell/>"  # NaN/inf have no ODF representation
        return (f'<table:table-cell office:value-type="float" '
                f'office:value="{value!r}"><text:p>{value}</text:p>'
                f'</table:table-cell>')
    text = escape(str(value))
    return (f'<table:table-cell office:value-type="string">'
            f'<text:p>{text}</text:p></table:table-cell>')


def _row(values: Iterable[Any]) -> str:
    return ("<table:table-row>"
            + "".join(_cell(v) for v in values)
            + "</table:table-row>")


class Sheet:
    """One tab: a name, a header row, and an iterable of rows.

    ``rows`` may be a generator — nothing here materialises it, which is what
    keeps a 600 000-row export from needing 600 000 rows' worth of memory.
    """

    def __init__(self, name: str, header: Sequence[str],
                 rows: Iterable[Sequence[Any]]):
        # ODF forbids these in a sheet name and LibreOffice truncates past 31.
        clean = "".join(c for c in str(name) if c not in "[]*?:/\\")[:31] or "Planilha"
        self.name = clean
        self.header = list(header)
        self.rows = rows


def sheet_from_dataframe(name: str, df, columns: Sequence[str] | None = None) -> Sheet:
    """A :class:`Sheet` over a pandas frame, iterated rather than copied."""
    cols = list(columns) if columns is not None else list(df.columns)
    frame = df[cols] if len(df) else df

    def rows() -> Iterator[list[Any]]:
        # itertuples beats iterrows by ~10x and keeps native types instead of
        # coercing every row to an object Series.
        for record in frame.itertuples(index=False, name=None):
            yield list(record)

    return Sheet(name, cols, rows())


def write(sheets: Sequence[Sheet]) -> bytes:
    """Assemble the sheets into ODS bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        # The mimetype entry must be first and STORED, per the ODF package
        # spec — it is how a file(1)-style sniffer identifies the format. A
        # deflated mimetype still opens in LibreOffice but is not conformant.
        archive.writestr(
            zipfile.ZipInfo("mimetype"), MIMETYPE, compress_type=zipfile.ZIP_STORED
        )
        archive.writestr("META-INF/manifest.xml", _MANIFEST)

        with archive.open("content.xml", "w") as stream:
            def emit(text: str) -> None:
                stream.write(text.encode("utf-8"))

            emit('<?xml version="1.0" encoding="UTF-8"?>\n'
                 f'<office:document-content {_NS}>'
                 '<office:body><office:spreadsheet>')

            for sheet in sheets:
                emit(f'<table:table table:name="{escape(sheet.name)}">'
                     f'<table:table-column '
                     f'table:number-columns-repeated="{max(1, len(sheet.header))}"/>')
                emit(_row(sheet.header))
                written = 0
                for values in sheet.rows:
                    written += 1
                    if written > MAX_ROWS_PER_SHEET:
                        raise SheetTooLarge(
                            f"A aba «{sheet.name}» passou de "
                            f"{MAX_ROWS_PER_SHEET:,} linhas.".replace(",", ".")
                        )
                    emit(_row(values))
                emit("</table:table>")
                logger.debug("ODS sheet %r: %s rows", sheet.name, written)

            emit("</office:spreadsheet></office:body></office:document-content>")

    return buffer.getvalue()
