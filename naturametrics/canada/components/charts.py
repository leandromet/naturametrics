"""Charts for the Canada page.

Three figures, one per panel: the ACI stacked history (the signature view, same
shape as Brazil's), the NTEMS age histogram, and the Hansen annual-loss series.

Kept separate from ``naturametrics/components/charts.py`` rather than
generalising it: that module reaches into ``config.mapbiomas`` for its stacking
order and palette, and parameterising it would mean threading a legend object
through every call for the sake of two callers. Two focused modules are the
smaller change.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..config import aafc
from ..config import forest as fc_cfg

_NO_DATA = {"pt": "Sem dados", "en": "No data"}


def _order_classes(class_ids: list[int]) -> list[int]:
    """Natural cover at the bottom, cropland above, water and no-data last —
    the same reading order the Brazil chart uses, so the two pages' stacked
    columns are comparable at a glance."""
    def key(c: int) -> tuple[int, int]:
        if c in aafc.STACK_PRIORITY:
            return (0, aafc.STACK_PRIORITY.index(c))
        if c in aafc.WATER:
            return (2, c)
        if c in aafc.NO_DATA:
            return (3, c)
        return (1, c)
    return sorted(class_ids, key=key)


def aci_history_figure(
    df: pd.DataFrame,
    radius_km: float,
    lang: str = "en",
    normalise: bool = False,
) -> go.Figure:
    """Stacked columns: one per year, segments coloured by AAFC class."""
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
        name = aafc.label(int(class_id), lang)
        fig.add_bar(
            x=years, y=values, name=name,
            marker_color=aafc.color(int(class_id)), marker_line_width=0,
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
        margin=dict(l=56, r=8, t=8, b=36), height=340,
        legend=dict(orientation="h", yanchor="top", y=-0.16, x=0,
                    font=dict(size=10), itemsizing="constant"),
        hovermode="x unified",
        # dtick=2, not 5: the ACI series is 17 years against MapBiomas' 40, so a
        # 5-year tick leaves only four labels across the whole axis.
        xaxis=dict(title=None, tickmode="linear", dtick=2, showgrid=False),
        yaxis=dict(title=y_title, showgrid=True, gridcolor="rgba(0,0,0,0.06)",
                   zeroline=False),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    if normalise:
        fig.update_yaxes(range=[0, 100])
    return fig


def forest_age_histogram_figure(
    df: pd.DataFrame, radius_km: float, lang: str = "en",
) -> go.Figure:
    """Forested area by NTEMS age bin for one buffer.

    No censored bin and no special colour for one — unlike Brazil, NTEMS reports
    a real age for every forest pixel, so the ramp runs the whole way.
    """
    fig = go.Figure()
    sub = pd.DataFrame()
    if df is not None and not df.empty and "radius_km" in df.columns:
        sub = df[df["radius_km"] == radius_km]

    if sub.empty:
        fig.add_annotation(text=_NO_DATA.get(lang, _NO_DATA["en"]),
                           showarrow=False, font=dict(size=13, color="#888"))
        return _style_age(fig, lang)

    grouped = sub.groupby("bin", as_index=False).agg(
        area_ha=("area_ha", "sum"), color=("color", "first"))
    order = {n: i for i, n in enumerate(fc_cfg.AGE_BIN_ORDER)}
    grouped["_o"] = grouped["bin"].map(lambda b: order.get(b, len(order)))
    grouped = grouped.sort_values("_o")

    fig.add_bar(
        x=grouped["bin"], y=grouped["area_ha"],
        marker_color=grouped["color"], marker_line_width=0,
        hovertemplate="<b>%{x}</b><br>%{y:,.1f} ha<extra></extra>",
    )
    return _style_age(fig, lang)


def _style_age(fig: go.Figure, lang: str) -> go.Figure:
    fig.update_layout(
        template="plotly_white", margin=dict(l=56, r=8, t=8, b=48), height=280,
        bargap=0.25, showlegend=False,
        xaxis=dict(title="Idade (anos)" if lang == "pt" else "Age (years)",
                   showgrid=False, categoryorder="array",
                   categoryarray=fc_cfg.AGE_BIN_ORDER),
        yaxis=dict(title="Área (ha)" if lang == "pt" else "Area (ha)",
                   showgrid=True, gridcolor="rgba(0,0,0,0.06)", zeroline=False),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def loss_by_year_figure(df: pd.DataFrame, lang: str = "en") -> go.Figure:
    """Annual Hansen tree-cover loss for one buffer.

    Loss only. Hansen's gain is a single undated flag for the whole record, so
    there is no gain series to pair with this — the total is shown as a number
    beside the chart instead of a fabricated line.
    """
    fig = go.Figure()
    if df is None or df.empty or "loss_ha" not in df.columns or df["loss_ha"].sum() <= 0:
        fig.add_annotation(text=_NO_DATA.get(lang, _NO_DATA["en"]),
                           showarrow=False, font=dict(size=11, color="#888"))
    else:
        fig.add_bar(
            x=df["year"], y=df["loss_ha"],
            marker_color=fc_cfg.HANSEN_LOSS_COLOR, marker_line_width=0,
            hovertemplate="<b>%{x}</b><br>%{y:,.1f} ha<extra></extra>",
        )
    fig.update_layout(
        template="plotly_white", margin=dict(l=48, r=8, t=8, b=32), height=170,
        showlegend=False, bargap=0.2,
        xaxis=dict(title=None, tickmode="linear", dtick=4, showgrid=False,
                   tickfont=dict(size=9)),
        yaxis=dict(title="ha", showgrid=True, gridcolor="rgba(0,0,0,0.06)",
                   zeroline=False, title_font=dict(size=10)),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig
