"""Recovery / readiness analysis page."""

from __future__ import annotations

from datetime import date

import streamlit as st

from ui.streamlit.charts.correlation import sleep_recovery_scatter
from ui.streamlit.charts.recovery import (
    contributor_bar,
    contributor_radar,
    hrv_trend,
    recovery_score_trend,
    recovery_vs_strain,
    resting_hr_trend,
)
from ui.streamlit.components.metrics import (
    inject_css,
    mini_metric,
    no_data_card,
    score_card,
    section_header,
)
from ui.streamlit.data import load_recovery_metrics, load_sleep_metrics


def render(user_id: str, start: date, end: date) -> None:
    inject_css()
    st.markdown("## Recovery & Readiness")

    records = load_recovery_metrics(user_id, start, end)

    if not records:
        no_data_card(
            f"No recovery data between {start} and {end}. "
            "Sync your Polar device and run the analytics pipeline."
        )
        return

    latest = records[-1]
    st.caption(
        f"Latest day: {latest.record_date.strftime('%A, %B %d %Y')} · "
        f"{len(records)} days in range"
    )

    # --- Latest day spotlight ----------------------------------------
    section_header("Latest day", latest.record_date.strftime("%B %d, %Y"))
    col_score, col_details = st.columns([1, 3])

    with col_score:
        score_card("Recovery score", latest.recovery_score)

    with col_details:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            hr = f"{latest.resting_hr_bpm:.0f} bpm" if latest.resting_hr_bpm else "—"
            mini_metric("Resting HR", hr)
        with c2:
            rmssd = f"{latest.rmssd_ms:.1f} ms" if latest.rmssd_ms else "—"
            mini_metric("RMSSD", rmssd)
        with c3:
            baseline = (
                f"{latest.hrv_baseline_ms:.1f} ms"
                if latest.hrv_baseline_ms else "—"
            )
            mini_metric("HRV baseline", baseline)
        with c4:
            temp = (
                f"{latest.mean_skin_temperature_celsius:.1f} °C"
                if latest.mean_skin_temperature_celsius else "—"
            )
            mini_metric("Skin temp", temp)

    # Contributor breakdown — bar + radar side by side
    section_header("Contributor breakdown", "How each signal drove today's score")
    col_bar, col_radar = st.columns(2)
    with col_bar:
        st.plotly_chart(contributor_bar(latest), use_container_width=True)
    with col_radar:
        st.plotly_chart(contributor_radar(latest), use_container_width=True)

    c = latest.contributors
    st.markdown(
        """<div style="font-size:12px;color:#8892b0;line-height:1.8;margin-bottom:8px;">
        <b style="color:#e0e0e0;">Weights:</b>
        Sleep quality 35% · HRV z-score 25% · Resting HR 20% ·
        Prev strain 10% · Recharge 4% · Skin temp 4% · Aerobic fitness 2%.
        <em>Missing signals fall back to neutral (50).</em>
        </div>""",
        unsafe_allow_html=True,
    )
    meta_cols = st.columns(5)
    with meta_cols[0]:
        if c.sleep_score is not None:
            st.metric("Sleep quality", f"{c.sleep_score:.0f} / 100")
        else:
            st.metric("Sleep quality", "—")
    with meta_cols[1]:
        if c.hrv_z_score is not None:
            sign = "+" if c.hrv_z_score >= 0 else ""
            st.metric("HRV z-score", f"{sign}{c.hrv_z_score:.2f} σ")
        else:
            st.metric("HRV z-score", "—")
    with meta_cols[2]:
        if c.resting_hr_z_score is not None:
            sign = "+" if c.resting_hr_z_score >= 0 else ""
            st.metric("Resting HR z-score", f"{sign}{c.resting_hr_z_score:.2f} σ")
        else:
            st.metric("Resting HR z-score", "—")
    with meta_cols[3]:
        if c.nightly_recharge_score is not None:
            st.metric("Nightly recharge", f"{c.nightly_recharge_score:.0f} / 100")
        else:
            st.metric("Nightly recharge", "—")
    with meta_cols[4]:
        if c.fitness_load_z_score is not None:
            sign = "+" if c.fitness_load_z_score >= 0 else ""
            st.metric("Fitness z-score", f"{sign}{c.fitness_load_z_score:.2f} σ")
        else:
            st.metric("Fitness z-score", "—")

    st.markdown("---")

    # --- Trend charts ------------------------------------------------
    section_header("Trends", f"Last {len(records)} days")

    st.plotly_chart(recovery_score_trend(records), use_container_width=True)

    col_left, col_right = st.columns(2)
    with col_left:
        fig = resting_hr_trend(records)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True)
        else:
            no_data_card("No resting HR data in this range.")

    with col_right:
        fig = hrv_trend(records)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True)
        else:
            no_data_card(
                "No RMSSD data. HRV is sourced from overnight PPI recordings — "
                "ensure the Polar app has nightly measurement enabled."
            )

    # Recovery vs strain correlation
    contrib_with_strain = [r for r in records if r.contributors.previous_strain_score is not None]
    if contrib_with_strain:
        section_header(
            "Recovery vs strain",
            "Visualise how yesterday's load affects today's readiness",
        )
        fig = recovery_vs_strain(records)
        if fig.data:
            st.plotly_chart(fig, use_container_width=True)

    # Sleep → next-day recovery correlation
    sleep_records = load_sleep_metrics(user_id, start, end)
    fig = sleep_recovery_scatter(sleep_records, records)
    if fig.data:
        section_header(
            "Sleep → recovery correlation",
            "Does better sleep predict next-day readiness?",
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- Data table --------------------------------------------------
    with st.expander("Raw data table"):
        import pandas as pd
        rows = []
        for r in reversed(records):
            rows.append({
                "Date": r.record_date,
                "Recovery": round(r.recovery_score, 1),
                "Resting HR": f"{r.resting_hr_bpm:.0f}" if r.resting_hr_bpm else "—",
                "RMSSD": f"{r.rmssd_ms:.1f}" if r.rmssd_ms else "—",
                "HR baseline": f"{r.resting_hr_baseline_bpm:.0f}" if r.resting_hr_baseline_bpm else "—",
                "Sleep contrib": f"{r.contributors.sleep_score:.0f}" if r.contributors.sleep_score else "—",
                "Recharge": f"{r.contributors.nightly_recharge_score:.0f}" if r.contributors.nightly_recharge_score else "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
