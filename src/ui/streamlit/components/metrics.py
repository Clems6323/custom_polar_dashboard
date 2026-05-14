"""Reusable metric card components for the dashboard.

All functions render directly into the Streamlit layout via st.* calls.
They accept pre-computed domain values and do NO data fetching.
"""

from __future__ import annotations

import streamlit as st

from ui.streamlit.theme import GREEN, MUTED, ORANGE, RED, score_color, score_label

# Inline CSS injected once per session
_CARD_CSS = """
<style>
.metric-card {
    background: #1a1d29;
    border: 1px solid #2d3142;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 8px;
}
.metric-card .label {
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #8892b0;
    margin-bottom: 8px;
}
.metric-card .score {
    font-size: 48px;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 4px;
}
.metric-card .sublabel {
    font-size: 13px;
    color: #8892b0;
    margin-top: 4px;
}
.metric-card .delta {
    font-size: 13px;
    font-weight: 600;
    margin-top: 6px;
}
.zone-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-top: 8px;
}
</style>
"""


def inject_css() -> None:
    """Inject card CSS once per session."""
    st.markdown(_CARD_CSS, unsafe_allow_html=True)


def score_card(
    label: str,
    score: float | None,
    sublabel: str = "",
    delta: float | None = None,
    invert: bool = False,
) -> None:
    """Render a prominent score card with colour-coded score and optional delta."""
    if score is None:
        st.markdown(
            f"""<div class="metric-card">
                <div class="label">{label}</div>
                <div class="score" style="color:{MUTED}">—</div>
                <div class="sublabel">No data</div>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    color = score_color(score, invert=invert)
    zone = score_label(score, invert=invert)

    delta_html = ""
    if delta is not None:
        sign = "+" if delta >= 0 else ""
        d_color = GREEN if (delta > 0) != invert else RED
        delta_html = f'<div class="delta" style="color:{d_color}">{sign}{delta:.1f} vs prev</div>'

    zone_color = color
    zone_bg = color + "22"

    parts = [
        f'<div class="metric-card">',
        f'<div class="label">{label}</div>',
        f'<div class="score" style="color:{color}">{score:.0f}</div>',
        f'<span class="zone-badge" style="background:{zone_bg};color:{zone_color};">{zone}</span>',
    ]
    if sublabel:
        parts.append(f'<div class="sublabel">{sublabel}</div>')
    if delta_html:
        parts.append(delta_html)
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def mini_metric(label: str, value: str, color: str = "#e0e0e0") -> None:
    """Compact label + value pair for detail rows."""
    st.markdown(
        f"""<div style="padding:8px 0;border-bottom:1px solid #2d3142;">
            <span style="color:#8892b0;font-size:12px;text-transform:uppercase;
                         letter-spacing:0.06em;">{label}</span><br>
            <span style="color:{color};font-size:18px;font-weight:600;">{value}</span>
        </div>""",
        unsafe_allow_html=True,
    )


def no_data_card(message: str = "No data available for this date range.") -> None:
    """Render a subtle empty-state placeholder."""
    st.markdown(
        f"""<div style="background:#1a1d29;border:1px dashed #2d3142;border-radius:12px;
                        padding:40px;text-align:center;color:#8892b0;font-size:14px;">
            {message}
        </div>""",
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = "") -> None:
    """Render a consistent section title."""
    sub_html = f"<br><span style='font-size:13px;color:#8892b0;'>{subtitle}</span>" if subtitle else ""
    st.markdown(
        f'<div style="margin:24px 0 12px;">'
        f'<span style="font-size:18px;font-weight:700;color:#e0e0e0;">{title}</span>'
        f"{sub_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def acwr_badge(acwr: float | None) -> None:
    """Render an ACWR zone badge inline."""
    if acwr is None:
        st.caption("ACWR: insufficient history (need 28 days)")
        return
    if acwr < 0.8:
        color, zone = "#4facfe", "Under-training"
    elif acwr <= 1.3:
        color, zone = GREEN, "Sweet spot"
    elif acwr <= 1.5:
        color, zone = ORANGE, "Caution"
    else:
        color, zone = RED, "Elevated risk"

    st.markdown(
        f"""<div style="margin:8px 0;">
            <span style="font-size:13px;color:#8892b0;">ACWR </span>
            <span style="font-size:16px;font-weight:700;color:{color};">{acwr:.2f}</span>
            <span class="zone-badge" style="background:{color}22;color:{color};margin-left:8px;">{zone}</span>
        </div>""",
        unsafe_allow_html=True,
    )
