"""Plotly chart builders for the Recovery page."""

from __future__ import annotations

import plotly.graph_objects as go

from domain.models.recovery import RecoveryMetrics
from ui.streamlit.theme import (
    BLUE,
    BORDER,
    GREEN,
    MUTED,
    ORANGE,
    PLOTLY_LAYOUT,
    PURPLE,
    RED,
    axis,
    score_color,
)


def recovery_score_trend(records: list[RecoveryMetrics]) -> go.Figure:
    """Area chart of composite recovery scores over time."""
    if not records:
        return go.Figure()

    dates = [r.record_date for r in records]
    scores = [r.recovery_score for r in records]
    colors = [score_color(s) for s in scores]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=scores, mode="lines+markers",
        line={"color": GREEN, "width": 2},
        marker={"color": colors, "size": 8, "line": {"width": 1, "color": "#0e1117"}},
        fill="tozeroy", fillcolor="rgba(0,201,167,0.08)",
        hovertemplate="<b>%{x}</b><br>Recovery: %{y:.0f}<extra></extra>",
    ))
    for y, label, color in [(67, "Optimal", GREEN), (34, "Fair", ORANGE)]:
        fig.add_hline(y=y, line_dash="dot", line_color=color, line_width=1,
                      annotation_text=label, annotation_font_size=10,
                      annotation_font_color=color)
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Recovery score",
        xaxis=axis(),
        yaxis=axis(range=[0, 100]),
        showlegend=False,
    )
    return fig


def resting_hr_trend(records: list[RecoveryMetrics]) -> go.Figure:
    """Line chart of resting HR over time."""
    hr_records = [r for r in records if r.resting_hr_bpm is not None]
    if not hr_records:
        return go.Figure()

    dates = [r.record_date for r in hr_records]
    hrs = [r.resting_hr_bpm for r in hr_records]
    baseline_vals = [r.resting_hr_baseline_bpm for r in hr_records if r.resting_hr_baseline_bpm]

    fig = go.Figure()
    if baseline_vals:
        mean_hr = sum(hrs) / len(hrs)
        baselines = [r.resting_hr_baseline_bpm or mean_hr for r in hr_records]
        fig.add_trace(go.Scatter(
            x=dates, y=baselines, mode="lines",
            line={"color": MUTED, "width": 1, "dash": "dot"},
            name="30-day baseline",
        ))

    fig.add_trace(go.Scatter(
        x=dates, y=hrs, mode="lines+markers",
        line={"color": RED, "width": 2}, marker={"size": 6},
        hovertemplate="<b>%{x}</b><br>Resting HR: %{y:.0f} bpm<extra></extra>",
        name="Resting HR",
    ))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Resting heart rate",
        xaxis=axis(),
        yaxis=axis(title="bpm"),
    )
    return fig


def hrv_trend(records: list[RecoveryMetrics]) -> go.Figure:
    """Line chart of overnight RMSSD."""
    hrv_records = [r for r in records if r.rmssd_ms is not None]
    if not hrv_records:
        return go.Figure()

    dates = [r.record_date for r in hrv_records]
    values = [r.rmssd_ms for r in hrv_records]
    baseline_vals = [r.hrv_baseline_ms for r in hrv_records if r.hrv_baseline_ms]

    fig = go.Figure()
    if baseline_vals:
        mean_hrv = sum(values) / len(values)
        baselines = [r.hrv_baseline_ms or mean_hrv for r in hrv_records]
        fig.add_trace(go.Scatter(
            x=dates, y=baselines, mode="lines",
            line={"color": MUTED, "width": 1, "dash": "dot"},
            name="30-day baseline",
        ))

    fig.add_trace(go.Scatter(
        x=dates, y=values, mode="lines+markers",
        line={"color": PURPLE, "width": 2}, marker={"size": 6},
        fill="tozeroy", fillcolor="rgba(181,123,238,0.08)",
        hovertemplate="<b>%{x}</b><br>RMSSD: %{y:.1f} ms<extra></extra>",
        name="RMSSD",
    ))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Overnight RMSSD (HRV)",
        xaxis=axis(),
        yaxis=axis(title="ms"),
    )
    return fig


def _z_to_pct(z: float | None, *, invert: bool = False) -> float:
    """Map a z-score to a 0-100 contributor value (mirrors the recovery_score formula)."""
    if z is None:
        return 50.0
    score = (max(-3.0, min(3.0, z)) + 3.0) / 6.0 * 100.0
    return 100.0 - score if invert else score


def _contributor_rows(
    record: RecoveryMetrics,
) -> list[tuple[str, float, str]]:
    """Return (label, display_value_0_100, raw_annotation) for every contributor."""
    c = record.contributors

    # Previous strain: invert so that high strain → low contributor value
    if c.previous_strain_score is not None:
        strain_display = max(0.0, 100.0 - c.previous_strain_score)
        strain_raw = f"strain {c.previous_strain_score:.0f} → inverted"
    else:
        strain_display = 50.0
        strain_raw = "no data"

    # Temperature: no sensor → neutral
    if c.temperature_deviation_celsius is not None:
        temp_display = max(0.0, min(100.0, 50.0 - c.temperature_deviation_celsius * 50.0))
        temp_raw = f"{c.temperature_deviation_celsius:+.2f} °C"
    else:
        temp_display = 50.0
        temp_raw = "no sensor"

    def _fmt_z(z: float | None, invert: bool = False) -> str:
        if z is None:
            return "no data"
        sign = "+" if z >= 0 else ""
        direction = "↓ below baseline" if z < 0 else "↑ above baseline"
        if invert:
            direction = "↓ good (lower HR)" if z < 0 else "↑ elevated HR"
        return f"{sign}{z:.2f} σ  ({direction})"

    hrv_display = _z_to_pct(c.hrv_z_score)
    hr_display = _z_to_pct(c.resting_hr_z_score, invert=True)

    sleep_display = c.sleep_score if c.sleep_score is not None else 50.0
    sleep_raw = f"{c.sleep_score:.0f} / 100" if c.sleep_score is not None else "no data"

    recharge_display = c.nightly_recharge_score if c.nightly_recharge_score is not None else 50.0
    recharge_raw = (
        f"{c.nightly_recharge_score:.0f} / 100"
        if c.nightly_recharge_score is not None else "no data"
    )

    fitness_display = _z_to_pct(c.fitness_load_z_score)
    fitness_raw = (
        _fmt_z(c.fitness_load_z_score) + "  (28-day load vs baseline)"
        if c.fitness_load_z_score is not None else "no cardio-load data synced"
    )

    return [
        ("Sleep quality (35%)", sleep_display, sleep_raw),
        ("HRV (25%)", hrv_display, _fmt_z(c.hrv_z_score)),
        ("Resting HR (20%)", hr_display, _fmt_z(c.resting_hr_z_score, invert=True)),
        ("Prev strain (10%)", strain_display, strain_raw),
        ("Nightly recharge (4%)", recharge_display, recharge_raw),
        ("Skin temp (4%)", temp_display, temp_raw),
        ("Aerobic fitness (2%)", fitness_display, fitness_raw),
    ]


def contributor_bar(record: RecoveryMetrics) -> go.Figure:
    """Horizontal bar chart of recovery score contributors for a single day."""
    rows = _contributor_rows(record)

    labels = [r[0] for r in rows]
    values = [round(r[1], 1) for r in rows]
    annotations = [r[2] for r in rows]
    colors = [score_color(v) for v in values]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=colors,
        customdata=annotations,
        hovertemplate="<b>%{y}</b><br>Score: %{x:.0f} / 100<br>%{customdata}<extra></extra>",
    ))
    fig.add_vline(x=50, line_dash="dot", line_color=MUTED, line_width=1)
    PLOTLY_LAYOUT_HORIZONTAL = PLOTLY_LAYOUT
    PLOTLY_LAYOUT_HORIZONTAL["hovermode"] = "y unified"
    fig.update_layout(
        **PLOTLY_LAYOUT_HORIZONTAL,
        title="Contributor breakdown",
        xaxis=axis(range=[0, 100]),
        yaxis=axis(showgrid=False),
        showlegend=False,
        height=320,
    )
    return fig


def contributor_radar(record: RecoveryMetrics) -> go.Figure:
    """Spider / radar chart of recovery score contributors for a single day."""
    rows = _contributor_rows(record)
    categories = [r[0].split(" (")[0] for r in rows]  # strip weight annotation
    values = [r[1] for r in rows]
    # Close the polygon
    cats_c = categories + [categories[0]]
    vals_c = values + [values[0]]
    neutral_c = [50.0] * len(cats_c)

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=neutral_c, theta=cats_c, mode="lines",
        line={"color": MUTED, "width": 1, "dash": "dot"},
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatterpolar(
        r=vals_c, theta=cats_c,
        fill="toself", fillcolor="rgba(79,172,254,0.12)",
        line={"color": BLUE, "width": 2},
        marker={"size": 6, "color": BLUE},
        hovertemplate="%{theta}: %{r:.0f}<extra></extra>",
        showlegend=False,
    ))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        polar={
            "bgcolor": "rgba(0,0,0,0)",
            "radialaxis": {
                "visible": True, "range": [0, 100],
                "gridcolor": BORDER,
                "tickfont": {"size": 10, "color": MUTED},
            },
            "angularaxis": {
                "gridcolor": BORDER,
                "tickfont": {"size": 11, "color": "#e0e0e0"},
            },
        },
        height=320,
    )
    return fig


def recovery_vs_strain(records: list[RecoveryMetrics]) -> go.Figure:
    """Dual-series chart: recovery score and previous strain contributor."""
    if not records:
        return go.Figure()

    dates = [r.record_date for r in records]
    rec_scores = [r.recovery_score for r in records]
    strain_vals = [r.contributors.previous_strain_score for r in records]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=rec_scores, mode="lines+markers",
        name="Recovery", line={"color": GREEN, "width": 2}, marker={"size": 6},
        hovertemplate="<b>%{x}</b><br>Recovery: %{y:.0f}<extra></extra>",
    ))

    non_null = [v for v in strain_vals if v is not None]
    if non_null:
        fig.add_trace(go.Scatter(
            x=dates, y=[v or 0 for v in strain_vals],
            mode="lines", name="Prev strain",
            line={"color": ORANGE, "width": 1.5, "dash": "dash"},
            hovertemplate="<b>%{x}</b><br>Prev strain: %{y:.0f}<extra></extra>",
        ))

    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Recovery vs previous strain",
        xaxis=axis(),
        yaxis=axis(range=[0, 100]),
    )
    return fig
