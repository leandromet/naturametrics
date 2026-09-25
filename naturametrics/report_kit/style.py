"""Page and type tokens shared by both renderers (doc/14 §2.4–2.5).

Every size the PDF and the HTML use comes from here, so the two formats and
the three apps keep one look. Colours are the umaterra neutral set; each app
passes only its accent through ``model.Brand``.
"""

from __future__ import annotations

# Page (A4 portrait, millimetres)
PAGE_W_MM = 210.0
PAGE_H_MM = 297.0
MARGIN_X_MM = 20.0
MARGIN_TOP_MM = 18.0
MARGIN_BOTTOM_MM = 18.0
HEADER_BAND_MM = 9.0          # pages 2+
FOOTER_BAND_MM = 8.0
TEXT_W_MM = PAGE_W_MM - 2 * MARGIN_X_MM          # 170

# Slots (R9) — the widths every image is produced for
SLOT_MM = {"full": 170.0, "half": 82.0}
GUTTER_MM = TEXT_W_MM - 2 * SLOT_MM["half"]      # 6
MAP_ASPECT = 110.0 / 170.0                       # full map 170 × 110 mm
LOCATOR_ASPECT = 0.9

# Resolution (R9): rasters at 150 dpi for their slot; charts laid out in CSS px
DPI = 150
CSS_DPI = 96
CHART_SCALE = DPI / CSS_DPI                       # 1.5625

# Type (points)
FONT_REGULAR = "NotoSans"
FONT_BOLD = "NotoSans-Bold"
FONT_ITALIC = "NotoSans-Italic"
FONT_SYMBOLS = "NotoSansMath"      # fallback for − → ≥ ≤ ↳ ≈ … (pdf._glyph_fallback)
BODY_PT = 9.5
BODY_LEADING = 13.5
H1_PT = 16.0
H2_PT = 12.5
CAPTION_PT = 8.5
SMALL_PT = 7.0
TABLE_PT = 8.0

# Colours
INK = "#1d1d1b"
MUTED = "#5f6368"
RULE = "#d0d4d9"
ZEBRA = "#f4f6f8"
PANEL = "#f3f3f3"
CALLOUT_COLORS = {
    "disclosure": ("#333333", "#f0f0f0"),      # (border, background)
    "note": ("#5f6368", "#f6f7f9"),
    "warning": ("#a15c00", "#fff8e6"),
}
PLACEHOLDER_BG = "#eceff2"


def mm_to_px(mm: float, dpi: int = DPI) -> int:
    return int(round(mm / 25.4 * dpi))


def slot_px(slot: str, dpi: int = DPI) -> int:
    """Raster width for a slot at ``dpi``: full ≈ 1004 px, half ≈ 484 px."""
    return mm_to_px(SLOT_MM[slot], dpi)
