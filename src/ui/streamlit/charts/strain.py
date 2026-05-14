"""Plotly chart builders for the Strain page."""

from __future__ import annotations

import plotly.graph_objects as go

from domain.models.strain import StrainMetrics
from ui.streamlit.theme import BLUE, GREEN, ORANGE, PLOTLY_LAYOUT, RED, axis, score_color


def training_load_bar(records: list[StrainMetrics]) -> go.Figure:
    """Bar chart of daily training load with strain-score colour coding."""
    if not records:
        return go.Figure()

    dates = [r.record_date for r in records]
    loads = [r.cardio_load for r in records]
    colors = [score_color(r.strain_score, invert=True) for r in records]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates,
        y=loads,
        marker_color=colors,
        customdata=[[r.strain_score, r.session_count] for r in records],
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Cardio load: %{y:.0f}<br>"
            "Strain score: %{customdata[0]:.0f}<br>"
            "Sessions: %{customdata[1]}<extra></extra>"
        ),
        name="Cardio load",
    ))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Daily cardio load",
        xaxis=axis(),
        yaxis=axis(title="load units"),
        showlegend=False,
    )
    return fig


def acwr_trend(records: list[StrainMetrics]) -> go.Figure:
    """Line chart of ACWR over time with risk-zone shading."""
    acwr_records = [r for r in records if r.acwr is not None]
    if not acwr_records:
        return go.Figure()

    dates = [r.record_date for r in acwr_records]
    values = [r.acwr for r in acwr_records]
    colors = [
        RED if v > 1.5 else (ORANGE if v > 1.3 else (GREEN if v >= 0.8 else BLUE))
        for v in values
    ]

    fig = go.Figure()
    for lo, hi, col in [
        (0, 0.8, "rgba(79,172,254,0.06)"),
        (0.8, 1.3, "rgba(0,201,167,0.06)"),
        (1.3, 1.5, "rgba(255,167,59,0.06)"),
        (1.5, 3.0, "rgba(255,107,107,0.06)"),
    ]:
        fig.add_hrect(y0=lo, y1=hi, fillcolor=col, layer="below", line_width=0)

    fig.add_trace(go.Scatter(
        x=dates, y=values, mode="lines+markers",
        line={"color": ORANGE, "width": 2},
        marker={"color": colors, "size": 8, "line": {"width": 1, "color": "#0e1117"}},
        hovertemplate="<b>%{x}</b><br>ACWR: %{y:.2f}<extra></extra>",
        name="ACWR",
    ))
    for y, color, label in [(1.5, RED, "Risk >1.5"), (0.8, BLUE, "Min 0.8")]:
        fig.add_hline(y=y, line_dash="dot", line_color=color, line_width=1,
                      annotation_text=label, annotation_font_size=10,
                      annotation_font_color=color)

    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Acute/Chronic Workload Ratio (ACWR)",
        xaxis=axis(),
        yaxis=axis(range=[0, min(max(values) + 0.3, 3.0)]),
        showlegend=False,
    )
    return fig


def strain_score_trend(records: list[StrainMetrics]) -> go.Figure:
    """Area chart of strain scores over time."""
    if not records:
        return go.Figure()

    dates = [r.record_date for r in records]
    scores = [r.strain_score for r in records]
    colors = [score_color(s, invert=True) for s in scores]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=scores, mode="lines+markers",
        line={"color": ORANGE, "width": 2},
        marker={"color": colors, "size": 7},
        fill="tozeroy", fillcolor="rgba(255,167,59,0.08)",
        hovertemplate="<b>%{x}</b><br>Strain: %{y:.0f}<extra></extra>",
    ))
    for y, label, color in [(67, "High", RED), (34, "Moderate", ORANGE)]:
        fig.add_hline(y=y, line_dash="dot", line_color=color, line_width=1,
                      annotation_text=label, annotation_font_size=10,
                      annotation_font_color=color)
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Strain score",
        xaxis=axis(),
        yaxis=axis(range=[0, 100]),
        showlegend=False,
    )
    return fig


def load_split_bar(records: list[StrainMetrics]) -> go.Figure:
    """Stacked bar showing cardio vs muscle load split."""
    with_loads = [r for r in records if r.muscle_load is not None]
    if not with_loads:
        return go.Figure()

    dates = [r.record_date for r in with_loads]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates, y=[r.cardio_load or 0 for r in with_loads],
        name="Cardio", marker_color=BLUE,
        hovertemplate="<b>%{x}</b><br>Cardio load: %{y:.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=dates, y=[r.muscle_load or 0 for r in with_loads],
        name="Muscle", marker_color=ORANGE,
        hovertemplate="<b>%{x}</b><br>Muscle load: %{y:.0f}<extra></extra>",
    ))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Load split (cardio vs muscle)",
        barmode="stack",
        xaxis=axis(),
        yaxis=axis(title="load units"),
    )
    return fig
