"""Charts.

The signature view is the land-cover history: one stacked column per year,
1985–2024, coloured with the **official MapBiomas palette** (doc/07-ui-ux.md §4).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go

from ..config import mapbiomas as mb

#: Classes are stacked in this order so the reading is stable across years:
#: natural formations at the bottom, anthropic above, water and no-data last.
_STACK_PRIORITY = (
    list(mb.FOREST_FORMATIONS) + list(mb.SAVANNA_FORMATIONS)
    + list(mb.NATURAL_NON_FOREST) + list(mb.PLANTED_FOREST)
)


def _order_classes(class_ids: list[int]) -> list[int]:
    def key(c: int) -> tuple[int, int]:
        if c in _STACK_PRIORITY:
            return (0, _STACK_PRIORITY.index(c))
        if c in mb.WATER:
            return (2, c)
        if c in mb.NO_DATA:
            return (3, c)
        return (1, c)
    return sorted(class_ids, key=key)


def land_cover_history_figure(
    df: pd.DataFrame,
    radius_km: float,
    lang: str = "pt",
    normalise: bool = False,
) -> go.Figure:
    """Stacked columns: one column per year, segments coloured by MapBiomas class.

    Args:
        normalise: plot percentage share instead of hectares.
    """
    fig = go.Figure()
    # An empty DataFrame has no columns at all, so the usual `.empty` check is
    # not enough — indexing it raises KeyError before we get there.
    if df is None or df.empty or "radius_km" not in df.columns:
        sub = df if df is not None else pd.DataFrame()
    else:
        sub = df[df["radius_km"] == radius_km]

    if sub.empty:
        fig.add_annotation(
            text="Sem dados" if lang == "pt" else "No data",
            showarrow=False, font=dict(size=13, color="#888"),
        )
        return _style(fig, radius_km, lang, normalise)

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
        name = mb.label(class_id, lang)
        fig.add_bar(
            x=years,
            y=values,
            name=name,
            marker_color=mb.color(class_id),
            marker_line_width=0,
            hovertemplate=f"<b>{name}</b><br>%{{x}}<br>%{{y:,.1f}} {unit}<extra></extra>",
        )

    return _style(fig, radius_km, lang, normalise)


def _style(fig: go.Figure, radius_km: float, lang: str, normalise: bool) -> go.Figure:
    unit = "%" if normalise else "ha"
    y_title = "Área (%)" if normalise else "Área (ha)"
    if lang != "pt":
        y_title = "Area (%)" if normalise else "Area (ha)"

    fig.update_layout(
        barmode="stack",
        bargap=0.06,
        template="plotly_white",
        margin=dict(l=56, r=8, t=8, b=36),
        height=340,
        legend=dict(
            orientation="h", yanchor="top", y=-0.16, x=0,
            font=dict(size=10), itemsizing="constant",
        ),
        hovermode="x unified",
        xaxis=dict(title=None, tickmode="linear", dtick=5, showgrid=False),
        yaxis=dict(title=y_title, ticksuffix="" if normalise else "", showgrid=True,
                   gridcolor="rgba(0,0,0,0.06)", zeroline=False),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    if normalise:
        fig.update_yaxes(range=[0, 100])
    return fig
