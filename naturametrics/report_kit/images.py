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
    full → 643×360 CSS px at scale 1.5625 ≈ 1004×563 px."""
    width = style.mm_to_px(style.SLOT_MM[slot], style.CSS_DPI)
    height = max(120, int(round(width * aspect)))
    return {"width": width, "height": height, "scale": style.CHART_SCALE}


def prepare_figure(fig_json: dict, slot: str = "full", aspect: float = 0.56) -> dict:
    """A copy of a Plotly figure dict made fit for a page: fixed size, white
    backgrounds (on-screen charts are transparent), fonts ≥ 10 px, long
    legends moved below, interactive widgets removed. No plotly import —
    this works on the plain dict (``fig.to_plotly_json()``)."""
    fig = copy.deepcopy(fig_json or {})
    layout = fig.setdefault("layout", {})
    opts = chart_opts(slot, aspect)
    layout["width"], layout["height"] = opts["width"], opts["height"]
    layout["autosize"] = False
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
    return fig


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
              height_mm: Optional[float] = None) -> bytes:
    """Re-encode ``data`` for a slot ``slot_mm`` wide at 150 dpi.

    Downsamples anything larger (never upsamples), then encodes imagery
    (``photo``) as JPEG q≈80 and charts / class rasters (``flat``) as PNG,
    palette-quantised when 256 colours or fewer suffice. Both renderers call
    this, so an oversized input can never inflate a report.
    """
    from PIL import Image   # lazy: the model and text layers never need Pillow

    fmt, width, height = image_size(data)
    if width * height > MAX_PIXELS:
        raise ValueError(f"image of {width}×{height} px exceeds {MAX_PIXELS} px")
    target_w = style.mm_to_px(slot_mm)
    target_h = style.mm_to_px(height_mm) if height_mm else None
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
