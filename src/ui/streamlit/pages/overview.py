"""Overview page — today's recovery, sleep, and strain at a glance."""

from __future__ import annotations

from datetime import date

import streamlit as st

from ui.streamlit.components.metrics import (
    inject_css,
    mini_metric,
    no_data_card,
    score_card,
    section_header,
)
from ui.streamlit.data import (
    date_range,
    latest_recovery,
    latest_sleep,
    latest_strain,
    load_recovery_metrics,
    load_sleep_metrics,
)


def _fmt_mins(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m:02d}m"


def render(user_id: str) -> None:
    inject_css()
    st.markdown("## Today's Overview")

    rec = latest_recovery(user_id)
    sleep = latest_sleep(user_id)
    strain = latest_strain(user_id)

    # Most recent date across available metrics
    latest_date: date | None = None
    for m in [rec, sleep, strain]:
        if m is not None:
            d = m.record_date
            if latest_date is None or d > latest_date:
                latest_date = d

    if latest_date:
        st.caption(f"Latest data: {latest_date.strftime('%A, %B %d %Y')}")
    else:
        st.caption("No data found. Run the sync script first.")

    st.markdown("---")

    # --- Score cards row -----------------------------------------
    col_r, col_s, col_t = st.columns(3)

    with col_r:
        delta_r = None
        score_card(
            "Recovery",
            rec.recovery_score if rec else None,
            sublabel=f"Data: {rec.record_date}" if rec else "",
            delta=delta_r,
        )

    with col_s:
        score_card(
            "Sleep",
            sleep.sleep_score if sleep else None,
            sublabel=f"Data: {sleep.record_date}" if sleep else "",
        )

    with col_t:
        score_card(
            "Strain",
            strain.strain_score if strain else None,
            sublabel=f"Data: {strain.record_date}" if strain else "",
            invert=True,
        )

    st.markdown("---")

    # --- Detail rows -----------------------------------------------
    section_header("Sleep details", "Last recorded night")
    if sleep:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            mini_metric("Total sleep", _fmt_mins(sleep.total_sleep_seconds))
        with c2:
            eff = f"{sleep.sleep_efficiency_pct:.0f}%" if sleep.sleep_efficiency_pct else "—"
            mini_metric("Efficiency", eff)
        with c3:
            deep = f"{sleep.deep_sleep_pct:.0f}%" if sleep.deep_sleep_pct else "—"
            mini_metric("Deep sleep", deep)
        with c4:
            rem = f"{sleep.rem_sleep_pct:.0f}%" if sleep.rem_sleep_pct else "—"
            mini_metric("REM sleep", rem)
    else:
        no_data_card("No sleep data. Sync your device and run the analytics pipeline.")

    section_header("Recovery details", "Last recorded day")
    if rec:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            hr = f"{rec.resting_hr_bpm:.0f} bpm" if rec.resting_hr_bpm else "—"
            mini_metric("Resting HR", hr)
        with c2:
            rmssd = f"{rec.rmssd_ms:.1f} ms" if rec.rmssd_ms else "—"
            mini_metric("RMSSD", rmssd)
        with c3:
            hrv_z = f"{rec.contributors.hrv_z_score:+.2f}" if rec.contributors.hrv_z_score else "—"
            mini_metric("HRV z-score", hrv_z)
        with c4:
            recharge = (
                f"{rec.contributors.nightly_recharge_score:.0f} / 100"
                if rec.contributors.nightly_recharge_score
                else "—"
            )
            mini_metric("Nightly recharge", recharge)
    else:
        no_data_card("No recovery data available.")

    if strain is None:
        section_header("Strain", "No activity sessions found")
        no_data_card(
            "No training sessions in the database. "
            "Sync exercise data with the Polar API and run the analytics pipeline."
        )

    st.markdown("---")

    # --- 7-day averages vs prior 7 days --------------------------------
    section_header("Weekly comparison", "This week vs last week")
    this_start, this_end = date_range(7)
    prev_start, prev_end = date_range(14)

    sleep_this = load_sleep_metrics(user_id, this_start, this_end)
    sleep_prev_all = load_sleep_metrics(user_id, prev_start, prev_end)
    sleep_prev = [r for r in sleep_prev_all if r not in sleep_this]

    rec_this = load_recovery_metrics(user_id, this_start, this_end)
    rec_prev_all = load_recovery_metrics(user_id, prev_start, prev_end)
    rec_prev = [r for r in rec_prev_all if r not in rec_this]

    def _avg(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    avg_sleep_this = _avg([r.sleep_score for r in sleep_this])
    avg_sleep_prev = _avg([r.sleep_score for r in sleep_prev])
    avg_rec_this = _avg([r.recovery_score for r in rec_this])
    avg_rec_prev = _avg([r.recovery_score for r in rec_prev])

    def _delta(this: float | None, prev: float | None) -> float | None:
        return round(this - prev, 1) if this is not None and prev is not None else None

    wc1, wc2, wc3, wc4 = st.columns(4)
    with wc1:
        val = f"{avg_sleep_this:.0f}" if avg_sleep_this is not None else "—"
        mini_metric("Sleep avg (7d)", val)
    with wc2:
        d = _delta(avg_sleep_this, avg_sleep_prev)
        mini_metric("vs prior week", f"{d:+.1f}" if d is not None else "—")
    with wc3:
        val = f"{avg_rec_this:.0f}" if avg_rec_this is not None else "—"
        mini_metric("Recovery avg (7d)", val)
    with wc4:
        d = _delta(avg_rec_this, avg_rec_prev)
        mini_metric("vs prior week", f"{d:+.1f}" if d is not None else "—")
