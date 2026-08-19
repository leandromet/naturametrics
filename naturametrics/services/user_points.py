"""Parsing a pasted coordinate list into points.

**No file upload, on purpose** — the user asked for paste-only specifically to avoid
the safety surface a file input opens (arbitrary bytes, MIME sniffing, size bombs,
zip/archive handling). A `<textarea>` has none of that: it is a string, already
capped at :data:`~naturametrics.config.settings.USER_POINTS_MAX_LINES` lines here,
and nothing downstream of this module ever touches a file path the user chose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..config.settings import USER_POINTS_MAX_LINES
from .geo import in_brazil, point as make_point

#: Shown in the "Enviar dados" panel and used verbatim in tests, so the two
#: cannot silently drift apart.
EXAMPLE_TEXT = (
    "# nome (opcional), latitude, longitude — um ponto por linha\n"
    "Fazenda Boa Vista, -9.50000, -63.00000\n"
    "-11.00000, -55.00000\n"
)

_SEPARATORS = re.compile(r"[,;\t]|\s{2,}")


@dataclass
class ParsedPoints:
    points: list[dict[str, Any]]
    errors: list[str]
    #: True when the paste had more valid lines than the cap and was cut short.
    truncated: bool
    total_valid_lines: int


def _split_fields(line: str) -> list[str]:
    """Comma/semicolon/tab first; falls back to plain whitespace so a line like
    ``-9.5 -63.0`` (no punctuation at all) still parses."""
    parts = [p.strip() for p in _SEPARATORS.split(line) if p.strip()]
    if len(parts) >= 2:
        return parts
    return [p for p in line.split() if p]


def _parse_line(line: str, line_no: int, seen_ids: set[str]) -> tuple[dict[str, Any] | None, str | None]:
    fields = _split_fields(line)
    if len(fields) < 2:
        return None, f"linha {line_no}: não foi possível interpretar «{line}»"

    if len(fields) >= 3:
        name, lat_raw, lon_raw = fields[0], fields[1], fields[2]
    else:
        name, lat_raw, lon_raw = "", fields[0], fields[1]

    try:
        lat, lon = float(lat_raw), float(lon_raw)
    except ValueError:
        return None, f"linha {line_no}: latitude/longitude inválidas em «{line}»"

    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None, f"linha {line_no}: coordenadas fora do intervalo válido em «{line}»"

    p = make_point(lat=lat, lon=lon)
    if not in_brazil(p):
        # Kept, not dropped: the point still lands on the map and the user
        # decides what to do with it. Only the Earth Engine analysis (already
        # guarded by validate_for_analysis at every entry point) will refuse it
        # later, with the same message a stray map click gets.
        note = f"linha {line_no}: {p} está fora do Brasil (mantido no mapa)"
    else:
        note = None

    pid = name or f"P{line_no}"
    if pid in seen_ids:
        pid = f"{pid}_{line_no}"
    seen_ids.add(pid)

    return {"id": pid, "lat": lat, "lon": lon}, note


def parse_coordinate_text(text: str) -> ParsedPoints:
    """Turn pasted text into points, one registry per line.

    Blank lines and lines starting with ``#`` are skipped silently — the latter
    is what lets :data:`EXAMPLE_TEXT`'s own header line double as a paste-ready
    template. Every other unparseable line is reported, not dropped silently:
    a coordinate list is exactly the kind of data where a quietly-skipped row is
    worse than an error the user can go fix.
    """
    points: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    valid = 0

    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parsed, note = _parse_line(line, i, seen_ids)
        if parsed is None:
            errors.append(note)
            continue
        valid += 1
        if note:
            errors.append(note)
        if len(points) < USER_POINTS_MAX_LINES:
            points.append(parsed)

    truncated = valid > USER_POINTS_MAX_LINES
    return ParsedPoints(points=points, errors=errors, truncated=truncated,
                        total_valid_lines=valid)
