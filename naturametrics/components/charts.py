"""Charts.

The signature view is the land-cover history: one stacked column per year,
1985–2024, coloured with the **official MapBiomas palette** (doc/07-ui-ux.md §4).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go

from ..config import vegetation_age as fa
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


# --------------------------------------------------------------------------- #
# Forest age (doc/10-forest-age.md, estimator E1) — deliberately a different
# look from the land-cover history above: its own palette (config/vegetation_age.py,
# carried over from the reference script rather than the MapBiomas coverage
# colours) and different chart shapes, since "age" and "land-cover history" are
# different questions even though they are computed from related products.
# --------------------------------------------------------------------------- #

_AGE_BIN_ORDER = [b[2] for b in fa.AGE_BIN_EDGES] + [fa.censored_label()]


def forest_age_line_figure(df: pd.DataFrame, lang: str = "pt") -> go.Figure:
    """Age at one pixel, year by year.

    A single trace that climbs while the pixel stays forested, drops to zero on
    every detected clearing, and either climbs again (regrowth) or plateaus at the
    censored ceiling (never disturbed in the DSV record) — see
    services.vegetation_age._forest_age_bands for why the ceiling is meaningful on its
    own, not an arbitrary cutoff.
    """
    fig = go.Figure()
    if df is None or df.empty or "age" not in df.columns:
        fig.add_annotation(
            text="Sem dados" if lang == "pt" else "No data",
            showarrow=False, font=dict(size=13, color="#888"),
        )
        return _style_age_line(fig, lang)

    name_col = "class_pt" if lang == "pt" else "class_en"
    fig.add_trace(go.Scatter(
        x=df["year"], y=df["age"], mode="lines+markers",
        line=dict(color="#2f6f4f", width=2),
        marker=dict(color=df["color"], size=7, line=dict(width=1, color="white")),
        customdata=df[name_col] if name_col in df.columns else df["class_pt"],
        hovertemplate=(
            "<b>%{x}</b><br>idade: %{y} anos<br>%{customdata}<extra></extra>"
            if lang == "pt" else
            "<b>%{x}</b><br>age: %{y} years<br>%{customdata}<extra></extra>"
        ),
        showlegend=False,
    ))

    fig.add_hline(
        y=fa.CENSORED_AGE,
        line=dict(color=fa.CENSORED_COLOR, width=1, dash="dot"),
        annotation_text=(f"teto do registro ({fa.CENSORED_AGE} anos)" if lang == "pt"
                         else f"record ceiling ({fa.CENSORED_AGE} years)"),
        annotation_position="bottom right",
        annotation_font=dict(size=9, color=fa.CENSORED_COLOR),
    )

    return _style_age_line(fig, lang)


def _style_age_line(fig: go.Figure, lang: str) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=48, r=8, t=8, b=36),
        height=280,
        hovermode="closest",
        xaxis=dict(title=None, tickmode="linear", dtick=5, showgrid=False),
        yaxis=dict(title="Idade (anos)" if lang == "pt" else "Age (years)",
                   showgrid=True, gridcolor="rgba(0,0,0,0.06)", zeroline=True,
                   rangemode="tozero"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def forest_age_histogram_figure(
    df: pd.DataFrame, radius_km: float, lang: str = "pt",
) -> go.Figure:
    """Area by age bin for one buffer — a snapshot, not a time series.

    The censored bin is deliberately not the ramp's last step: doc/10 §6 warns
    that a continuous ramp running into "censored" reads as "even older" rather
    than "unknown, possibly far older", so it gets config.vegetation_age.CENSORED_COLOR
    instead, a colour that does not belong to the dated ramp at all.
    """
    fig = go.Figure()
    sub = pd.DataFrame()
    if df is not None and not df.empty and "radius_km" in df.columns:
        sub = df[df["radius_km"] == radius_km]

    if sub.empty:
        fig.add_annotation(
            text="Sem dados" if lang == "pt" else "No data",
            showarrow=False, font=dict(size=13, color="#888"),
        )
        return _style_age_hist(fig, lang)

    grouped = sub.groupby("bin", as_index=False).agg(
        area_ha=("area_ha", "sum"), color=("color", "first"))
    grouped["order"] = grouped["bin"].apply(
        lambda b: _AGE_BIN_ORDER.index(b) if b in _AGE_BIN_ORDER else len(_AGE_BIN_ORDER))
    grouped = grouped.sort_values("order")

    unit = "ha"
    fig.add_bar(
        x=grouped["bin"], y=grouped["area_ha"],
        marker_color=grouped["color"], marker_line_width=0,
        hovertemplate=f"<b>%{{x}}</b><br>%{{y:,.1f}} {unit}<extra></extra>",
    )

    return _style_age_hist(fig, lang)


def change_bar_figure(loss_ha: float, gain_ha: float, lang: str = "pt") -> go.Figure:
    """Loss vs. regrowth since the Forest Code baseline (2008), for one buffer.

    Deliberately just two bars — this sits in the leftover space below the age
    summary column (results.py `_age_summary_line`), not a chart in its own
    right. `services.change_mask` already computes this per buffer for the map
    layer toggle; this is its first appearance as a number you can read.
    """
    from ..services import change_mask as cm

    fig = go.Figure()
    labels = cm.CHANGE_LABELS_PT if lang == "pt" else cm.CHANGE_LABELS_EN
    names = [labels[cm.CHANGE_LOSS], labels[cm.CHANGE_GAIN]]
    values = [loss_ha, gain_ha]
    colors = [cm.CHANGE_COLORS[cm.CHANGE_LOSS], cm.CHANGE_COLORS[cm.CHANGE_GAIN]]

    if loss_ha <= 0 and gain_ha <= 0:
        fig.add_annotation(
            text="Sem dados" if lang == "pt" else "No data",
            showarrow=False, font=dict(size=11, color="#888"),
        )
    else:
        # Columns, not horizontal bars: the space this sits in (results.py, the
        # leftover room below the age summary lines) is taller than it is wide,
        # and a horizontal bar's value label sits to the *right* of the bar —
        # exactly the direction this column is narrowest in, so a large number
        # ran past the edge and was clipped. Above a column there is no such
        # ceiling: the y-axis range is padded past the tallest bar for it.
        fig.add_bar(
            x=names, y=values,
            marker_color=colors, marker_line_width=0,
            text=[f"{v:,.0f} ha".replace(",", ".") for v in values],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{x}</b><br>%{y:,.1f} ha<extra></extra>",
        )

    fig.update_layout(
        template="plotly_white",
        margin=dict(l=4, r=4, t=20, b=4),
        height=150,
        showlegend=False,
        xaxis=dict(title=None, showgrid=False, tickfont=dict(size=10)),
        yaxis=dict(visible=False, range=[0, max(values, default=1) * 1.35]),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        bargap=0.45,
    )
    return fig


def _style_age_hist(fig: go.Figure, lang: str) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=56, r=8, t=8, b=56),
        height=280,
        bargap=0.25,
        xaxis=dict(title=None, showgrid=False, tickangle=-20,
                   categoryorder="array", categoryarray=_AGE_BIN_ORDER),
        yaxis=dict(title="Área (ha)" if lang == "pt" else "Area (ha)",
                   showgrid=True, gridcolor="rgba(0,0,0,0.06)", zeroline=False),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig


# --------------------------------------------------------------------------- #
# Above-ground biomass (services.biomass, ESA CCI Biomass_cci v6.0) — its own
# palette again, and its own shape: ten snapshots (2007, 2010, 2015-2022), not
# a continuous run, joined with lines for readability but with real gaps.
# --------------------------------------------------------------------------- #

def biomass_history_figure(df: pd.DataFrame, radius_km: float, lang: str = "pt") -> go.Figure:
    """Mean above-ground biomass per hectare, year by year, for one buffer.

    Error bars are the per-pixel standard deviation reduced to a mean over the
    buffer (services.biomass) — a rough uncertainty band, not a rigorous
    confidence interval on the buffer's own mean.
    """
    fig = go.Figure()
    sub = pd.DataFrame()
    if df is not None and not df.empty and "radius_km" in df.columns:
        sub = df[df["radius_km"] == radius_km].sort_values("year")

    if sub.empty:
        fig.add_annotation(
            text="Sem dados" if lang == "pt" else "No data",
            showarrow=False, font=dict(size=13, color="#888"),
        )
        return _style_biomass(fig, lang, [])

    sd = sub["agb_sd_mgha"].fillna(0.0)
    unit_label = "Mg/ha"
    fig.add_trace(go.Scatter(
        x=sub["year"], y=sub["agb_mean_mgha"], mode="lines+markers",
        line=dict(color="#3c6e47", width=2),
        marker=dict(color="#3c6e47", size=7, line=dict(width=1, color="white")),
        error_y=dict(type="data", array=sd, visible=True,
                     color="rgba(60,110,71,0.35)", thickness=1.5),
        customdata=sd,
        hovertemplate=(
            f"<b>%{{x}}</b><br>%{{y:.1f}} ± %{{customdata:.1f}} {unit_label}"
            "<extra></extra>"
        ),
        showlegend=False,
    ))

    return _style_biomass(fig, lang, sorted(sub["year"].unique().tolist()))


def _style_biomass(fig: go.Figure, lang: str, years: list[int]) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=48, r=8, t=8, b=36),
        height=280,
        hovermode="closest",
        xaxis=dict(title=None, showgrid=False,
                   tickmode="array", tickvals=years),
        yaxis=dict(
            title="Biomassa acima do solo (Mg/ha)" if lang == "pt"
            else "Above-ground biomass (Mg/ha)",
            showgrid=True, gridcolor="rgba(0,0,0,0.06)", zeroline=True,
            rangemode="tozero",
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig
