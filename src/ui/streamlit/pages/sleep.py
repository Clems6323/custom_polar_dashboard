"""Sleep analysis page."""

from __future__ import annotations

from datetime import date

import streamlit as st

from ui.streamlit.charts.sleep import (
    sleep_architecture_stack,
    sleep_consistency_trend,
    sleep_duration_trend,
    sleep_efficiency_trend,
    sleep_schedule,
    sleep_score_trend,
)
from ui.streamlit.components.metrics import (
    inject_css,
    mini_metric,
    no_data_card,
    score_card,
    section_header,
)
from ui.streamlit.data import load_sleep_metrics, load_sleep_sessions


def _fmt_mins(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m:02d}m"


def render(user_id: str, start: date, end: date) -> None:
    inject_css()
    st.markdown("## Sleep Analysis")

    records = load_sleep_metrics(user_id, start, end)

    if not records:
        no_data_card(
            f"No sleep data between {start} and {end}. "
            "Sync your Polar device and run the analytics pipeline."
        )
        return

    latest = records[-1]
    st.caption(
        f"Latest night: {latest.record_date.strftime('%A, %B %d %Y')} · "
        f"{len(records)} nights in range"
    )

    # --- Last night spotlight ----------------------------------------
    section_header("Last night", latest.record_date.strftime("%B %d, %Y"))
    col_score, col_details = st.columns([1, 3])

    with col_score:
        score_card("Sleep score", latest.sleep_score)

    with col_details:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            mini_metric("Duration", _fmt_mins(latest.total_sleep_seconds))
        with c2:
            eff = f"{latest.sleep_efficiency_pct:.0f}%" if latest.sleep_efficiency_pct else "—"
            mini_metric("Efficiency", eff)
        with c3:
            lat = (
                f"{latest.sleep_latency_seconds / 60:.0f} min"
                if latest.sleep_latency_seconds else "—"
            )
            mini_metric("Latency", lat)
        with c4:
            cons = (
                f"{latest.sleep_consistency_score:.0f} / 100"
                if latest.sleep_consistency_score else "—"
            )
            mini_metric("Consistency", cons)

        # Stage + interruption decomposition (all % of time in bed)
        if latest.deep_sleep_pct is not None:
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                mini_metric("Deep", f"{latest.deep_sleep_pct:.0f}%", color="#4facfe")
            with c2:
                rem = f"{latest.rem_sleep_pct:.0f}%" if latest.rem_sleep_pct else "—"
                mini_metric("REM", rem, color="#b57bee")
            with c3:
                light = f"{latest.light_sleep_pct:.0f}%" if latest.light_sleep_pct else "—"
                mini_metric("Light", light, color="#8892b0")
            with c4:
                intr = f"{latest.awake_pct:.0f}%" if latest.awake_pct else "—"
                mini_metric("Interruptions", intr, color="#ff6b6b")
            with c5:
                mini_metric("Unknown", f"{(latest.unknown_sleep_pct or 0):.0f}%", color="#6c757d")

        # Short / long interruption breakdown
        if (
            latest.short_interruption_duration_seconds is not None
            or latest.long_interruption_duration_seconds is not None
        ):
            c1, c2 = st.columns(2)
            with c1:
                short_min = (
                    f"{latest.short_interruption_duration_seconds / 60:.0f} min"
                    if latest.short_interruption_duration_seconds is not None else "—"
                )
                mini_metric("Short interruptions", short_min)
            with c2:
                long_min = (
                    f"{latest.long_interruption_duration_seconds / 60:.0f} min"
                    if latest.long_interruption_duration_seconds is not None else "—"
                )
                mini_metric("Long interruptions", long_min)

    st.markdown("---")

    # --- Trend charts ------------------------------------------------
    section_header("Trends", f"Last {len(records)} nights")

    col_left, col_right = st.columns(2)
    with col_left:
        fig = sleep_score_trend(records)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        fig = sleep_duration_trend(records)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True)

    col_left, col_right = st.columns(2)
    with col_left:
        fig = sleep_architecture_stack(records)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True)
        else:
            no_data_card("No sleep stage data available.")

    with col_right:
        fig = sleep_efficiency_trend(records)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True)
        else:
            no_data_card("No efficiency data available.")

    # Consistency chart (full width)
    fig = sleep_consistency_trend(records)
    if fig.data:
        section_header(
            "Schedule consistency",
            "Rolling 7-night bedtime, wake time, and duration regularity",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Sleep schedule (bedtime / wake time)
    sessions = load_sleep_sessions(user_id, start, end)
    fig = sleep_schedule(sessions)
    if fig.data:
        section_header("Sleep schedule", "Bedtime and wake time over the period")
        st.plotly_chart(fig, use_container_width=True)

    # --- Data table --------------------------------------------------
    with st.expander("Raw data table"):
        import pandas as pd
        rows = []
        for r in reversed(records):
            rows.append({
                "Date": r.record_date,
                "Score": round(r.sleep_score, 1),
                "Duration": _fmt_mins(r.total_sleep_seconds),
                "Efficiency": f"{r.sleep_efficiency_pct:.0f}%" if r.sleep_efficiency_pct else "—",
                "Deep %": f"{r.deep_sleep_pct:.0f}%" if r.deep_sleep_pct else "—",
                "REM %": f"{r.rem_sleep_pct:.0f}%" if r.rem_sleep_pct else "—",
                "Short interruptions": (
                    f"{r.short_interruption_duration_seconds / 60:.0f} min"
                    if r.short_interruption_duration_seconds is not None else "—"
                ),
                "Long interruptions": (
                    f"{r.long_interruption_duration_seconds / 60:.0f} min"
                    if r.long_interruption_duration_seconds is not None else "—"
                ),
                "Consistency": f"{r.sleep_consistency_score:.0f}" if r.sleep_consistency_score else "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
