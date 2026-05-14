"""Strain / training load analysis page."""

from __future__ import annotations

from datetime import date

import streamlit as st

from ui.streamlit.charts.strain import (
    acwr_trend,
    load_split_bar,
    strain_score_trend,
    training_load_bar,
)
from ui.streamlit.components.metrics import (
    acwr_badge,
    inject_css,
    mini_metric,
    no_data_card,
    score_card,
    section_header,
)
from ui.streamlit.data import load_strain_metrics


def render(user_id: str, start: date, end: date) -> None:
    inject_css()
    st.markdown("## Strain & Training Load")

    records = load_strain_metrics(user_id, start, end)

    if not records:
        no_data_card(
            "No training session data available.\n\n"
            "Sync your Polar exercises and run the analytics pipeline "
            "(`python scripts/run_analytics.py`) to populate strain metrics."
        )
        st.info(
            "Strain metrics are computed from exercise sessions recorded in your Polar account. "
            "If you have no exercise data in the selected date range, this page will remain empty.",
            icon="ℹ️",
        )
        return

    latest = records[-1]
    st.caption(
        f"Latest day: {latest.record_date.strftime('%A, %B %d %Y')} · "
        f"{len(records)} days with sessions in range"
    )

    # --- Latest day spotlight ----------------------------------------
    section_header("Latest day", latest.record_date.strftime("%B %d, %Y"))
    col_score, col_details = st.columns([1, 3])

    with col_score:
        score_card("Strain score", latest.strain_score, invert=True)

    with col_details:
        c1, c2, c3 = st.columns(3)
        with c1:
            cardio = f"{latest.cardio_load:.0f}" if latest.cardio_load else "—"
            mini_metric("Cardio load", cardio)
        with c2:
            muscle = f"{latest.muscle_load:.0f}" if latest.muscle_load else "—"
            mini_metric("Muscle load", muscle)
        with c3:
            mini_metric("Sessions", str(latest.session_count))

        acwr_badge(latest.acwr)

    st.markdown("---")

    # --- Trend charts ------------------------------------------------
    section_header("Trends", f"{len(records)} days with training data")

    col_left, col_right = st.columns(2)
    with col_left:
        fig = training_load_bar(records)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        fig = strain_score_trend(records)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True)

    # ACWR (full width — important signal)
    acwr_records = [r for r in records if r.acwr is not None]
    if acwr_records:
        section_header("ACWR", "Acute/Chronic Workload Ratio — injury risk indicator")
        fig = acwr_trend(records)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Sweet spot: 0.8–1.3 | Caution: 1.3–1.5 | Elevated risk: > 1.5 "
            "(Gabbett TJ, 2016 Br J Sports Med)"
        )

    # Load split
    split_records = [r for r in records if r.cardio_load is not None]
    if split_records:
        fig = load_split_bar(records)
        if fig.data:
            section_header("Load split")
            st.plotly_chart(fig, use_container_width=True)

    # --- Data table --------------------------------------------------
    with st.expander("Raw data table"):
        import pandas as pd
        rows = []
        for r in reversed(records):
            rows.append({
                "Date": r.record_date,
                "Strain": round(r.strain_score, 1),
                "Cardio load": round(r.cardio_load, 1) if r.cardio_load else "—",
                "Muscle load": round(r.muscle_load, 1) if r.muscle_load else "—",
                "ACWR": f"{r.acwr:.2f}" if r.acwr else "—",
                "Sessions": r.session_count,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
