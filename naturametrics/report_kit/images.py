"""Image rules (R9): screen quality, sized to the page — doc/14 §2.5.

Every raster a report embeds is produced for the slot it fills at 150 dpi and
never larger. Charts are laid out at their on-page CSS size and rasterised at
``scale = 150/96`` so Plotly's pixel font sizes print at their nominal point
size beside 9.5 pt body text; a chart laid out 1000 px wide and shrunk to
170 mm would print its 12 px labels at about 6 pt.
"""

from __future__ import annotations

import base64
import copy
import io
import struct
from typing import Literal, Optional, Tuple

from . import style

MAX_PIXELS = 40_000_000          # refuse anything larger before decoding
PNG_SIG = b"\x89PNG\r\n\x1a\n"

ImageKind = Literal["photo", "flat"]


def chart_opts(slot: str = "full", aspect: float = 0.56) -> dict:
    """Plotly/kaleido export options for a chart filling ``slot``:
    full → 643×360 CSS px at scale ≈ 2.29 ≈ 1473×826 px (220 dpi)."""
    width = style.mm_to_px(style.SLOT_MM[slot], style.CSS_DPI)
    height = max(120, int(round(width * aspect)))
    return {"width": width, "height": height, "scale": style.CHART_SCALE}


#: A chart may be at most this tall relative to its width on the page
#: (170 mm × 1.3 ≈ 221 mm, inside A4's 261 mm text height).
MAX_CHART_ASPECT = 1.3
#: Below this share of the height left for the plot itself, the figure's
#: fixed pixel margins are judged to have eaten the chart (see _decide_size).
MIN_PLOT_SHARE = 0.45


def _decide_size(fig: dict, slot: str, aspect: float) -> Tuple[int, int]:
    """(width, height) in CSS px for a figure on the page.

    Normally the slot's width at ``aspect``. But plotly margins are fixed
    pixels: a figure designed with big margins for context rows (Yvynation's
    deforestation timeline: 1183 px tall, 843 px of margins) squeezed to
    643×399 px has *no* plot left — every trace crushed onto one line. When
    the margins would leave less than MIN_PLOT_SHARE of the height, the
    figure keeps its designed height and the layout is widened instead
    (capped at MAX_CHART_ASPECT), so the whole chart scales down together
    and the plot keeps its proportions.
    """
    base = chart_opts(slot, aspect)
    layout = fig.get("layout") or {}
    margin = layout.get("margin") or {}
    fixed = float(margin.get("t") or 80) + float(margin.get("b") or 80)
    if fixed <= base["height"] * (1 - MIN_PLOT_SHARE):
        return base["width"], base["height"]
    designed = float(layout.get("height") or 0)
    # The designer's height when it leaves a usable plot (it may be mostly
    # context rows on purpose); otherwise enough for a 260 px plot.
    height = int(round(designed if designed - fixed >= 200 else fixed + 260))
    width = max(base["width"], int(round(height / MAX_CHART_ASPECT)))
    return width, height


def prepare_figure(fig_json: dict, slot: str = "full", aspect: float = 0.56) -> dict:
    """A copy of a Plotly figure dict made fit for a page: its size (see
    _decide_size), white backgrounds (on-screen charts are transparent),
    fonts ≥ 10 px, long legends moved below, interactive widgets removed. No
    plotly import — this works on the plain dict (``fig.to_plotly_json()``).

    Rasterise it with ``figure_opts(prepared, slot)``, never with separately
    computed numbers: the size decided here is the one to render at."""
    fig = copy.deepcopy(fig_json or {})
    layout = fig.setdefault("layout", {})
    layout["paper_bgcolor"] = "#ffffff"
    layout["plot_bgcolor"] = "#ffffff"
    font = layout.setdefault("font", {})
    font["size"] = max(10, int(font.get("size") or 10))
    font.setdefault("family", "Noto Sans, Arial, sans-serif")
    layout.pop("updatemenus", None)
    layout.pop("sliders", None)
    traces = [tr for tr in fig.get("data", []) if tr.get("showlegend", True)]
    if len(traces) > 6:
        legend = layout.setdefault("legend", {})
        legend.update({"orientation": "h", "yanchor": "top", "y": -0.18,
                       "xanchor": "left", "x": 0})
        margin = layout.setdefault("margin", {})
        margin["b"] = max(int(margin.get("b") or 0), 90)
    title = layout.get("title")
    if isinstance(title, dict) and title.get("font"):
        title["font"]["size"] = max(11, int(title["font"].get("size") or 11))
    data = fig.get("data") or []
    if data and all(tr.get("type") == "sankey" for tr in data):
        # No axes to make room for: plotly's web defaults (80/80/100/80 px)
        # would waste a third of the page width. Only fills unset sides.
        margin = layout.setdefault("margin", {})
        has_title = bool(title.get("text") if isinstance(title, dict) else title)
        for side, value in (("l", 10), ("r", 10), ("b", 10), ("t", 45 if has_title else 10)):
            margin.setdefault(side, value)
    layout["width"], layout["height"] = _decide_size(fig, slot, aspect)
    layout["autosize"] = False
    return fig


def figure_opts(prepared: dict, slot: str = "full") -> dict:
    """Plotly.toImage / kaleido options for a figure from ``prepare_figure``:
    its own layout size, at the scale that makes the raster exactly the slot's
    width at CHART_DPI (≈ 2.29 for an ordinary chart, less for a widened one)."""
    layout = (prepared or {}).get("layout") or {}
    width = int(layout.get("width") or chart_opts(slot)["width"])
    height = int(layout.get("height") or chart_opts(slot)["height"])
    return {"width": width, "height": height,
            "scale": style.slot_px(slot, style.CHART_DPI) / width}


def image_size(data: bytes) -> Tuple[str, int, int]:
    """(format, width, height) from the header alone — PNG IHDR or JPEG SOF —
    so an oversized image is refused before any decoding allocates it."""
    if data[:8] == PNG_SIG and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return "png", width, height
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack(">HH", data[i + 5:i + 9])
                return "jpeg", width, height
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seg
        raise ValueError("JPEG without a frame header")
    raise ValueError("not a PNG or JPEG image")


def decode_data_url(data_url: str, max_bytes: int = 3_000_000) -> bytes:
    """``data:image/png;base64,…`` → PNG bytes, refusing anything else."""
    prefix = "data:image/png;base64,"
    if not isinstance(data_url, str) or not data_url.startswith(prefix):
        raise ValueError("expected a data:image/png;base64 URL")
    if (len(data_url) - len(prefix)) * 3 // 4 > max_bytes:
        raise ValueError("image too large")
    raw = base64.b64decode(data_url[len(prefix):], validate=True)
    if raw[:8] != PNG_SIG:
        raise ValueError("payload is not a PNG")
    return raw


def fit_image(data: bytes, slot_mm: float, kind: ImageKind = "flat",
              height_mm: Optional[float] = None, dpi: int = style.DPI) -> bytes:
    """Re-encode ``data`` for a slot ``slot_mm`` wide at ``dpi`` (150 for
    maps/imagery; charts pass style.CHART_DPI).

    Downsamples anything larger (never upsamples), then encodes imagery
    (``photo``) as JPEG q≈80 and charts / class rasters (``flat``) as PNG,
    palette-quantised when 256 colours or fewer suffice. Both renderers call
    this, so an oversized input can never inflate a report.
    """
    from PIL import Image   # lazy: the model and text layers never need Pillow

    fmt, width, height = image_size(data)
    if width * height > MAX_PIXELS:
        raise ValueError(f"image of {width}×{height} px exceeds {MAX_PIXELS} px")
    target_w = style.mm_to_px(slot_mm, dpi)
    target_h = style.mm_to_px(height_mm, dpi) if height_mm else None
    img = Image.open(io.BytesIO(data))
    img.load()
    scale = min(1.0, target_w / img.width,
                (target_h / img.height) if target_h else 1.0)
    if scale < 1.0:
        img = img.resize((max(1, int(round(img.width * scale))),
                          max(1, int(round(img.height * scale)))),
                         Image.LANCZOS)
    out = io.BytesIO()
    if kind == "photo":
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(out, "JPEG", quality=80, optimize=True, subsampling=2)
        return out.getvalue()
    if img.mode == "P":
        img.save(out, "PNG", optimize=True)
        return out.getvalue()
    has_alpha = img.mode in ("RGBA", "LA")
    rgb = img.convert("RGBA" if has_alpha else "RGB")
    colors = rgb.getcolors(maxcolors=256)
    if colors is not None:
        method = Image.Quantize.FASTOCTREE if has_alpha else Image.Quantize.MEDIANCUT
        rgb = rgb.quantize(colors=max(2, len(colors)), method=method)
    rgb.save(out, "PNG", optimize=True)
    return out.getvalue()
