"""Cross-domain correlation chart builders."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import plotly.graph_objects as go

from domain.models.recovery import RecoveryMetrics
from domain.models.sleep_metrics import SleepMetrics
from ui.streamlit.theme import BLUE, MUTED, PLOTLY_LAYOUT, axis


def sleep_recovery_scatter(
    sleep_records: list[SleepMetrics],
    recovery_records: list[RecoveryMetrics],
) -> go.Figure:
    """Scatter of sleep score (day D) vs next-day recovery score (day D+1).

    Pairs each sleep night with the recovery recorded on the following day.
    Annotates the Pearson r in the chart title.
    """
    if not sleep_records or not recovery_records:
        return go.Figure()

    rec_by_date = {r.record_date: r.recovery_score for r in recovery_records}

    xs, ys, labels = [], [], []
    for s in sleep_records:
        rec_score = rec_by_date.get(s.record_date + timedelta(days=1))
        if rec_score is not None:
            xs.append(s.sleep_score)
            ys.append(rec_score)
            labels.append(str(s.record_date))

    if len(xs) < 3:
        return go.Figure()

    xs_arr = np.array(xs, dtype=float)
    ys_arr = np.array(ys, dtype=float)
    m, b = np.polyfit(xs_arr, ys_arr, 1)
    r = float(np.corrcoef(xs_arr, ys_arr)[0, 1])

    x_range = [float(xs_arr.min()), float(xs_arr.max())]
    y_trend = [m * x + b for x in x_range]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_range, y=y_trend, mode="lines",
        line={"color": MUTED, "width": 1, "dash": "dot"},
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers",
        marker={
            "size": 9, "color": BLUE, "opacity": 0.85,
            "line": {"width": 1, "color": "#0e1117"},
        },
        customdata=labels,
        hovertemplate=(
            "<b>%{customdata}</b><br>"
            "Sleep: %{x:.0f}<br>"
            "Next-day recovery: %{y:.0f}<extra></extra>"
        ),
        showlegend=False,
    ))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=f"Sleep score → next-day recovery  (r = {r:+.2f}, n = {len(xs)})",
        xaxis=axis(title="Sleep score", range=[0, 100]),
        yaxis=axis(title="Recovery score", range=[0, 100]),
    )
    return fig
