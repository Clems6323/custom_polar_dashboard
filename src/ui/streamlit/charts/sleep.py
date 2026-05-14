"""Plotly chart builders for the Sleep page.

All functions return ``go.Figure`` objects — they do NOT call st.plotly_chart.
Callers decide column layout and sizing.
"""

from __future__ import annotations

import plotly.graph_objects as go

from domain.models.sleep import SleepSession
from domain.models.sleep_metrics import SleepMetrics
from ui.streamlit.theme import (
    BLUE,
    GREEN,
    MUTED,
    ORANGE,
    PLOTLY_LAYOUT,
    PURPLE,
    RED,
    SLEEP_STAGE_COLORS,
    axis,
    score_color,
)


def sleep_score_trend(records: list[SleepMetrics]) -> go.Figure:
    """Line chart of sleep scores over time with colour-coded markers."""
    if not records:
        return go.Figure()

    dates = [r.record_date for r in records]
    scores = [r.sleep_score for r in records]
    colors = [score_color(s) for s in scores]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=scores,
            mode="lines+markers",
            line={"color": BLUE, "width": 2},
            marker={"color": colors, "size": 8, "line": {"width": 1, "color": "#0e1117"}},
            fill="tozeroy",
            fillcolor="rgba(79,172,254,0.08)",
            hovertemplate="<b>%{x}</b><br>Sleep score: %{y:.0f}<extra></extra>",
            name="Sleep score",
        )
    )
    for y, label, color in [(67, "Good", GREEN), (34, "Fair", ORANGE)]:
        fig.add_hline(y=y, line_dash="dot", line_color=color, line_width=1,
                      annotation_text=label, annotation_font_size=10,
                      annotation_font_color=color)
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Sleep score",
        xaxis=axis(),
        yaxis=axis(range=[0, 100]),
        showlegend=False,
    )
    return fig


def sleep_duration_trend(records: list[SleepMetrics]) -> go.Figure:
    """Bar chart of sleep duration (hours) with 7.5h target line."""
    if not records:
        return go.Figure()

    dates = [r.record_date for r in records]
    hours = [round(r.total_sleep_seconds / 3600, 2) for r in records]
    bar_colors = [GREEN if h >= 7.0 else (ORANGE if h >= 6.0 else RED) for h in hours]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates,
        y=hours,
        marker_color=bar_colors,
        hovertemplate="<b>%{x}</b><br>Sleep: %{y:.1f} h<extra></extra>",
        name="Duration",
    ))
    fig.add_hline(y=7.5, line_dash="dot", line_color=MUTED, line_width=1,
                  annotation_text="7.5h target", annotation_font_size=10,
                  annotation_font_color=MUTED)
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Sleep duration (hours)",
        xaxis=axis(),
        yaxis=axis(title="hours"),
        showlegend=False,
    )
    return fig


def sleep_architecture_stack(records: list[SleepMetrics]) -> go.Figure:
    """Stacked bar chart of time-in-bed decomposition: DEEP / REM / LIGHT / INTERRUPTIONS / UNKNOWN."""
    if not records:
        return go.Figure()

    with_stages = [r for r in records if r.deep_sleep_pct is not None]
    if not with_stages:
        return go.Figure()

    dates = [r.record_date for r in with_stages]
    fig = go.Figure()

    for stage, color, field in [
        ("Deep", SLEEP_STAGE_COLORS["DEEP"], "deep_sleep_pct"),
        ("REM", SLEEP_STAGE_COLORS["REM"], "rem_sleep_pct"),
        ("Light", SLEEP_STAGE_COLORS["LIGHT"], "light_sleep_pct"),
        ("Interruptions", RED, "awake_pct"),
        ("Unknown", MUTED, "unknown_sleep_pct"),
    ]:
        vals = [getattr(r, field) or 0.0 for r in with_stages]
        fig.add_trace(go.Bar(
            x=dates, y=vals, name=stage, marker_color=color,
            hovertemplate=f"<b>%{{x}}</b><br>{stage}: %{{y:.1f}}% of bed<extra></extra>",
        ))

    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Sleep architecture (% of time in bed)",
        barmode="stack",
        xaxis=axis(),
        yaxis=axis(title="% of time in bed", range=[0, 105]),
    )
    return fig


def sleep_efficiency_trend(records: list[SleepMetrics]) -> go.Figure:
    """Line chart of sleep efficiency % with 90% target."""
    eff_records = [r for r in records if r.sleep_efficiency_pct is not None]
    if not eff_records:
        return go.Figure()

    dates = [r.record_date for r in eff_records]
    effs = [r.sleep_efficiency_pct for r in eff_records]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=effs, mode="lines+markers",
        line={"color": PURPLE, "width": 2}, marker={"size": 6},
        fill="tozeroy", fillcolor="rgba(181,123,238,0.08)",
        hovertemplate="<b>%{x}</b><br>Efficiency: %{y:.1f}%<extra></extra>",
        name="Efficiency",
    ))
    fig.add_hline(y=90, line_dash="dot", line_color=GREEN, line_width=1,
                  annotation_text="90% target", annotation_font_size=10,
                  annotation_font_color=GREEN)
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Sleep efficiency",
        xaxis=axis(),
        yaxis=axis(range=[50, 100], ticksuffix="%"),
        showlegend=False,
    )
    return fig


def sleep_consistency_trend(records: list[SleepMetrics]) -> go.Figure:
    """Area chart of the rolling 7-night consistency score."""
    consistency_records = [r for r in records if r.sleep_consistency_score is not None]
    if not consistency_records:
        return go.Figure()

    dates = [r.record_date for r in consistency_records]
    scores = [r.sleep_consistency_score for r in consistency_records]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=scores, mode="lines",
        line={"color": GREEN, "width": 2},
        fill="tozeroy", fillcolor="rgba(0,201,167,0.08)",
        hovertemplate="<b>%{x}</b><br>Consistency: %{y:.0f}<extra></extra>",
    ))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="7-night schedule consistency",
        xaxis=axis(),
        yaxis=axis(range=[0, 100]),
        showlegend=False,
    )
    return fig


def _fmt_ampm(hours: float) -> str:
    h = int(hours) % 24
    m = int((hours % 1) * 60)
    period = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {period}"


def sleep_schedule(sessions: list[SleepSession]) -> go.Figure:
    """Scatter of bedtime and wake time over date.

    Bedtime is normalized so midnight = 24.0, 1 AM = 25.0, etc., keeping
    the axis continuous when users go to bed before vs after midnight.
    """
    if not sessions:
        return go.Figure()

    dates, bedtimes, waketimes = [], [], []
    for s in sessions:
        dates.append(s.end_time.date())
        bh = s.start_time.hour + s.start_time.minute / 60
        bedtimes.append(bh + 24 if bh < 12 else bh)
        wh = s.end_time.hour + s.end_time.minute / 60
        waketimes.append(wh + 24 if wh < 12 else wh)

    all_vals = bedtimes + waketimes
    y_min = max(18.0, min(all_vals) - 0.5)
    y_max = min(34.0, max(all_vals) + 0.5)

    tick_map = {
        18: "6 PM", 19: "7 PM", 20: "8 PM", 21: "9 PM", 22: "10 PM",
        23: "11 PM", 24: "Midnight", 25: "1 AM", 26: "2 AM", 27: "3 AM",
        28: "4 AM", 29: "5 AM", 30: "6 AM", 31: "7 AM", 32: "8 AM",
        33: "9 AM", 34: "10 AM",
    }
    tick_vals = [v for v in tick_map if y_min <= v <= y_max]
    tick_texts = [tick_map[v] for v in tick_vals]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=bedtimes, mode="markers+lines",
        name="Bedtime",
        line={"color": PURPLE, "width": 1.5},
        marker={"size": 7, "color": PURPLE},
        text=[_fmt_ampm(b) for b in bedtimes],
        hovertemplate="<b>%{x}</b><br>Bedtime: %{text}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=waketimes, mode="markers+lines",
        name="Wake time",
        line={"color": ORANGE, "width": 1.5},
        marker={"size": 7, "color": ORANGE},
        text=[_fmt_ampm(w) for w in waketimes],
        hovertemplate="<b>%{x}</b><br>Wake: %{text}<extra></extra>",
    ))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Sleep schedule",
        xaxis=axis(),
        yaxis=axis(tickvals=tick_vals, ticktext=tick_texts, range=[y_min, y_max]),
    )
    return fig
