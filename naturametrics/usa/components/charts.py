"""Charts for the USA page.

Two figures, one per panel: the NLCD stacked history (the signature view, same
shape as Brazil's) and the Hansen annual-loss series.

Kept separate from ``naturametrics/components/charts.py`` rather than
generalising it: that module reaches into ``config.mapbiomas`` for its stacking
order and palette, and parameterising it would mean threading a legend object
through every call for the sake of two callers. Two focused modules are the
smaller change.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..config import nlcd
from ..config import forest as fc_cfg

_NO_DATA = {"pt": "Sem dados", "en": "No data"}


def _order_classes(class_ids: list[int]) -> list[int]:
    """Natural cover at the bottom, cropland above, water and no-data last —
    the same reading order the Brazil chart uses, so the two pages' stacked
    columns are comparable at a glance."""
    def key(c: int) -> tuple[int, int]:
        if c in nlcd.STACK_PRIORITY:
            return (0, nlcd.STACK_PRIORITY.index(c))
        if c in nlcd.WATER:
            return (2, c)
        if c in nlcd.NO_DATA:
            return (3, c)
        return (1, c)
    return sorted(class_ids, key=key)


def nlcd_history_figure(
    df: pd.DataFrame,
    radius_km: float,
    lang: str = "en",
    normalise: bool = False,
) -> go.Figure:
    """Stacked columns: one per year, segments coloured by NLCD class."""
    fig = go.Figure()
    if df is None or df.empty or "radius_km" not in df.columns:
        sub = df if df is not None else pd.DataFrame()
    else:
        sub = df[df["radius_km"] == radius_km]

    if sub.empty:
        fig.add_annotation(text=_NO_DATA.get(lang, _NO_DATA["en"]),
                           showarrow=False, font=dict(size=13, color="#888"))
        return _style(fig, lang, normalise)

    value_col = "area_ha"
    if normalise:
        sub = sub.copy()
        totals = sub.groupby("year")["area_ha"].transform("sum")
        sub["area_pct"] = sub["area_ha"] / totals * 100.0
        value_col = "area_pct"

    years = sorted(sub["year"].unique())
    unit = "%" if normalise else "ha"

    for class_id in _order_classes(sorted(sub["class_id"].unique())):
        rows = sub[sub["class_id"] == class_id].set_index("year")
        values = [float(rows[value_col].get(y, 0.0)) for y in years]
        if not any(values):
            continue
        name = nlcd.label(int(class_id), lang)
        fig.add_bar(
            x=years, y=values, name=name,
            marker_color=nlcd.color(int(class_id)), marker_line_width=0,
            hovertemplate=f"<b>{name}</b><br>%{{x}}<br>%{{y:,.1f}} {unit}<extra></extra>",
        )
    return _style(fig, lang, normalise)


def _style(fig: go.Figure, lang: str, normalise: bool) -> go.Figure:
    if lang == "pt":
        y_title = "Área (%)" if normalise else "Área (ha)"
    else:
        y_title = "Area (%)" if normalise else "Area (ha)"
    fig.update_layout(
        barmode="stack", bargap=0.06, template="plotly_white",
        # See naturametrics/components/charts.py's own `_style()` for the
        # full rationale on both changes below (ported):
        # - b=84/height=400: the legend can wrap to several rows on a
        #   phone-width chart where it only ever needed one on desktop.
        # - dragmode/fixedrange: stops a one-finger touch on the chart from
        #   being captured as a zoom gesture instead of scrolling past it.
        margin=dict(l=56, r=8, t=8, b=84), height=400,
        legend=dict(orientation="h", yanchor="top", y=-0.14, x=0,
                    font=dict(size=9), itemsizing="constant", tracegroupgap=2),
        hovermode="x unified",
        dragmode=False,
        # dtick=5: NLCD runs 1985–2025, 41 years like MapBiomas.
        xaxis=dict(title=None, tickmode="linear", dtick=5, showgrid=False,
                   fixedrange=True),
        yaxis=dict(title=y_title, showgrid=True, gridcolor="rgba(0,0,0,0.06)",
                   zeroline=False, fixedrange=True),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    if normalise:
        fig.update_yaxes(range=[0, 100])
    return fig


_L = {
    "annual_loss": {"en": "Annual loss", "pt": "Perda anual"},
    "cum_loss": {"en": "Cumulative loss", "pt": "Perda acumulada"},
    "gain_total": {
        "en": f"Gain {fc_cfg.HANSEN_GAIN_YEAR_START}–{fc_cfg.HANSEN_GAIN_YEAR_END}",
        "pt": f"Ganho {fc_cfg.HANSEN_GAIN_YEAR_START}–{fc_cfg.HANSEN_GAIN_YEAR_END}",
    },
    "gain_window": {"en": "gain window", "pt": "janela do ganho"},
}


def loss_by_year_figure(
    df: pd.DataFrame,
    gain_total_ha: float = 0.0,
    lang: str = "en",
) -> go.Figure:
    """Hansen tree-cover loss over time, against the gain total.

    **Why gain is a horizontal line and not a series.** Hansen publishes ``loss``
    with a per-pixel ``lossyear``, so annual loss is real data. ``gain`` carries
    no year — it is a bitmask flag — so there is no annual gain to plot. Drawing
    one would mean inventing the year dimension.

    **And why the shaded band matters.** Gain covers **2000–2012 only** and, in
    the dataset's own words, "has not been updated in subsequent versions". So
    the dashed gain level is comparable with the cumulative-loss curve *only up
    to 2012*. The shaded region marks exactly that window; past its right edge
    the red curve keeps climbing against a green line that stopped being
    maintained, and comparing the two there would be reading a 25-year loss
    against a 13-year gain.

    (An annual gain series *could* be derived from the AAFC crop inventory's
    forest classes, and deliberately is not: measured on a stable forested BC
    buffer it returns 200–800 ha of gain and 200–1100 ha of loss per year in a
    7 854 ha area, against Hansen's ~1 500 ha of loss across 25 years. That is
    classification flicker, not change.)
    """
    fig = go.Figure()
    has_loss = (df is not None and not df.empty and "loss_ha" in df.columns
                and float(df["loss_ha"].sum()) > 0)

    if not has_loss and gain_total_ha <= 0:
        fig.add_annotation(text=_NO_DATA.get(lang, _NO_DATA["en"]),
                           showarrow=False, font=dict(size=11, color="#888"))
        return _style_loss(fig, lang)

    if has_loss:
        cumulative = df["loss_ha"].cumsum()
        fig.add_bar(
            x=df["year"], y=df["loss_ha"],
            name=_L["annual_loss"].get(lang, _L["annual_loss"]["en"]),
            marker_color=fc_cfg.HANSEN_LOSS_COLOR, marker_line_width=0,
            hovertemplate="<b>%{x}</b><br>%{y:,.1f} ha<extra></extra>",
        )
        fig.add_trace(go.Scatter(
            x=df["year"], y=cumulative, mode="lines",
            name=_L["cum_loss"].get(lang, _L["cum_loss"]["en"]),
            line=dict(color="#7a1710", width=2),
            hovertemplate="<b>%{x}</b><br>%{y:,.1f} ha<extra></extra>",
        ))

    if gain_total_ha > 0:
        # The window gain actually covers. Drawn first so it sits behind the
        # data, and drawn at all so the eye stops comparing past its right edge.
        fig.add_vrect(
            x0=fc_cfg.HANSEN_LOSS_YEAR_START - 0.5,
            x1=fc_cfg.HANSEN_GAIN_YEAR_END + 0.5,
            fillcolor=fc_cfg.HANSEN_GAIN_COLOR, opacity=0.07,
            layer="below", line_width=0,
            annotation_text=_L["gain_window"].get(lang, _L["gain_window"]["en"]),
            annotation_position="top left",
            annotation_font=dict(size=8, color="#6b8f6b"),
        )
        # A level, not a series — and only meaningful inside the band above.
        fig.add_hline(
            y=gain_total_ha,
            line=dict(color=fc_cfg.HANSEN_GAIN_COLOR, width=2, dash="dash"),
            annotation_text=_L["gain_total"].get(lang, _L["gain_total"]["en"]),
            annotation_position="bottom right",
            annotation_font=dict(size=9, color=fc_cfg.HANSEN_GAIN_COLOR),
        )

    return _style_loss(fig, lang)


def _style_loss(fig: go.Figure, lang: str) -> go.Figure:
    fig.update_layout(
        template="plotly_white", margin=dict(l=46, r=8, t=8, b=26), height=185,
        bargap=0.2,
        legend=dict(orientation="h", yanchor="top", y=-0.18, x=0,
                    font=dict(size=9)),
        hovermode="x unified",
        dragmode=False,
        xaxis=dict(title=None, tickmode="linear", dtick=4, showgrid=False,
                   tickfont=dict(size=9), fixedrange=True),
        yaxis=dict(title="ha", showgrid=True, gridcolor="rgba(0,0,0,0.06)",
                   zeroline=False, title_font=dict(size=10),
                   tickfont=dict(size=9), fixedrange=True),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# --------------------------------------------------------------------------- #
# LCMS disturbance and MTBS fire: stacked columns by class, one column per year
# --------------------------------------------------------------------------- #
def class_history_figure(df: pd.DataFrame, radius_km: float, lang: str = "en",
                         stack_order: list[int] | None = None) -> go.Figure:
    """Stacked columns of area (ha) per year, coloured by class (LCMS change class or MTBS
    severity); needs the ``class_id``/``class_en``/``class_pt``/``color`` columns."""
    fig = go.Figure()
    sub = pd.DataFrame()
    if df is not None and not df.empty and "radius_km" in df.columns:
        sub = df[df["radius_km"] == radius_km]
    if sub.empty:
        fig.add_annotation(text=_NO_DATA.get(lang, _NO_DATA["en"]), showarrow=False,
                           font=dict(size=13, color="#888"))
    else:
        years = list(range(int(sub["year"].min()), int(sub["year"].max()) + 1))
        name_col = "class_pt" if lang == "pt" else "class_en"
        order = stack_order or sorted(sub["class_id"].unique())
        for cid in [c for c in order if c in set(sub["class_id"])]:
            by = sub[sub["class_id"] == cid].set_index("year")
            vals = [float(by["area_ha"].get(y, 0.0)) for y in years]
            fig.add_bar(x=years, y=vals, name=str(by[name_col].iloc[0]),
                        marker_color=str(by["color"].iloc[0]), marker_line_width=0,
                        hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>%{y:,.1f} ha<extra></extra>")
    fig.update_layout(
        barmode="stack", bargap=0.08, template="plotly_white", height=300,
        margin=dict(l=56, r=8, t=8, b=84), hovermode="x unified", dragmode=False,
        legend=dict(orientation="h", yanchor="top", y=-0.16, x=0, font=dict(size=9),
                    itemsizing="constant", tracegroupgap=2),
        xaxis=dict(title=None, tickmode="linear", dtick=5, showgrid=False, fixedrange=True),
        yaxis=dict(title="Área (ha)" if lang == "pt" else "Area (ha)", showgrid=True,
                   gridcolor="rgba(0,0,0,0.06)", zeroline=False, fixedrange=True),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig


def age_histogram_figure(df: pd.DataFrame, radius_km: float, lang: str = "en") -> go.Figure:
    """Tree area by years since the last disturbance. The last bin is censored by the 1985 start:
    it is the one that says "not disturbed since then", not an age."""
    from ..config import disturbance as dcfg

    fig = go.Figure()
    sub = pd.DataFrame()
    if df is not None and not df.empty and "radius_km" in df.columns:
        sub = df[df["radius_km"] == radius_km]
    if sub.empty:
        fig.add_annotation(text=_NO_DATA.get(lang, _NO_DATA["en"]), showarrow=False,
                           font=dict(size=13, color="#888"))
    else:
        g = sub.groupby("bin", as_index=False).agg(area_ha=("area_ha", "sum"), color=("color", "first"))
        g["_o"] = g["bin"].map(lambda b: dcfg.AGE_ORDER.index(b) if b in dcfg.AGE_ORDER else 99)
        g = g.sort_values("_o")
        fig.add_bar(x=g["bin"], y=g["area_ha"], marker_color=g["color"], marker_line_width=0,
                    hovertemplate="<b>%{x}</b><br>%{y:,.1f} ha<extra></extra>")
    fig.update_layout(
        template="plotly_white", height=240, margin=dict(l=56, r=8, t=8, b=56), dragmode=False,
        xaxis=dict(title="Anos desde o último distúrbio" if lang == "pt" else "Years since last disturbance",
                   fixedrange=True),
        yaxis=dict(title="Área (ha)" if lang == "pt" else "Area (ha)", fixedrange=True,
                   gridcolor="rgba(0,0,0,0.06)"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
    return fig


def canopy_figure(df: pd.DataFrame, lang: str = "en") -> go.Figure:
    """Mean tree canopy cover (%) by year, one line per radius."""
    fig = go.Figure()
    if df is None or df.empty:
        fig.add_annotation(text=_NO_DATA.get(lang, _NO_DATA["en"]), showarrow=False,
                           font=dict(size=13, color="#888"))
    else:
        for radius in sorted(df["radius_km"].unique()):
            sub = df[df["radius_km"] == radius].sort_values("year")
            fig.add_scatter(x=sub["year"], y=sub["canopy_pct"], mode="lines", name=f"{radius:g} km",
                            hovertemplate=f"{radius:g} km · %{{x}}: %{{y:.1f}}%<extra></extra>")
    fig.update_layout(
        template="plotly_white", height=240, margin=dict(l=56, r=8, t=8, b=50), dragmode=False,
        legend=dict(orientation="h", yanchor="top", y=-0.22, x=0, font=dict(size=9)),
        xaxis=dict(tickmode="linear", dtick=5, fixedrange=True, showgrid=False),
        yaxis=dict(title="Dossel arbóreo (%)" if lang == "pt" else "Tree canopy (%)", fixedrange=True,
                   gridcolor="rgba(0,0,0,0.06)", rangemode="tozero"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig


def biomass_chart(df: pd.DataFrame, radius_km: float, lang: str = "en") -> go.Figure:
    """Mean above-ground biomass (Mg/ha) by year for one radius, with the product's own uncertainty
    as a band (ESA CCI). Years are the product's snapshot years, so the gaps are real gaps."""
    fig = go.Figure()
    sub = pd.DataFrame()
    if df is not None and not df.empty and "radius_km" in df.columns:
        sub = df[df["radius_km"] == radius_km].sort_values("year")
    if sub.empty:
        fig.add_annotation(text="Sem dados" if lang == "pt" else "No data", showarrow=False,
                           font=dict(size=13, color="#888"))
    else:
        x = [int(y) for y in sub["year"]]
        m = [float(v) for v in sub["agb_mean_mgha"]]
        sd = [float(v) if v == v else 0.0 for v in sub["agb_sd_mgha"]]
        hi = [a + b for a, b in zip(m, sd)]
        lo = [max(0.0, a - b) for a, b in zip(m, sd)]
        fig.add_scatter(x=x + x[::-1], y=hi + lo[::-1], fill="toself", mode="lines", line=dict(width=0),
                        fillcolor="rgba(31,141,73,0.15)", hoverinfo="skip", showlegend=False)
        fig.add_scatter(x=x, y=m, mode="lines+markers", line=dict(color="#1f8d49"), marker=dict(size=7),
                        name="Mg/ha", hovertemplate="%{x}: %{y:.1f} Mg/ha<extra></extra>")
    fig.update_layout(
        template="plotly_white", height=240, margin=dict(l=56, r=8, t=8, b=44), dragmode=False,
        showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title=None, tickmode="array", tickvals=[2007, 2010, 2015, 2017, 2019, 2022],
                   fixedrange=True, showgrid=False),
        yaxis=dict(title="Mg/ha" if lang != "pt" else "Mg/ha", fixedrange=True,
                   gridcolor="rgba(0,0,0,0.06)", rangemode="tozero"),
    )
    return fig
