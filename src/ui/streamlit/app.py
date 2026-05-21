"""Polar Dashboard — Streamlit application entry point.

Run with:
    streamlit run src/ui/streamlit/app.py

Or via the Makefile:
    make dashboard
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

# Ensure src/ and project root are on the path when launched directly
_src = Path(__file__).resolve().parent.parent.parent
_root = _src.parent
for _p in (_root, _src):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import streamlit as st  # noqa: E402

# Page config must be the first Streamlit call
st.set_page_config(
    page_title="Polar Dashboard",
    page_icon="❤️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Hide Streamlit's auto-generated multipage nav (pages/ folder is detected automatically)
st.markdown(
    "<style>[data-testid='stSidebarNav']{display:none}</style>",
    unsafe_allow_html=True,
)

from ui.streamlit.data import date_range, resolve_user_id  # noqa: E402
from ui.streamlit.pages import metrics_guide, overview, recovery, sleep, strain  # noqa: E402
from ui.streamlit.sync import (  # noqa: E402
    exchange_auth_code,
    get_auth_url,
    get_last_sync_info,
    is_token_available,
    run_full_sync,
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        """<div style="text-align:center;padding:16px 0 8px;">
            <span style="font-size:28px;">❤️</span><br>
            <span style="font-size:18px;font-weight:700;color:#e0e0e0;">Polar Dashboard</span><br>
            <span style="font-size:11px;color:#8892b0;letter-spacing:0.08em;">PHYSIOLOGICAL ANALYTICS</span>
        </div>""",  # noqa: E501
        unsafe_allow_html=True,
    )
    st.markdown("---")

    page = st.radio(
        "Navigate",
        options=["Overview", "Sleep", "Strain", "Recovery", "Metrics Guide"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown(
        "<span style='font-size:12px;color:#8892b0;text-transform:uppercase;"
        "letter-spacing:0.08em;'>Date range</span>",
        unsafe_allow_html=True,
    )

    today = date.today()
    preset = st.selectbox(
        "Range preset",
        ["Last 7 days", "Last 14 days", "Last 30 days", "Last 60 days", "Custom"],
        index=2,
        label_visibility="collapsed",
    )

    preset_days = {"Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30, "Last 60 days": 60}
    if preset == "Custom":
        start_date = st.date_input("From", value=today - timedelta(days=30))
        end_date = st.date_input("To", value=today)
    else:
        days = preset_days[preset]
        start_date, end_date = date_range(days)

    st.markdown("---")
    user_id = resolve_user_id()
    if user_id:
        st.markdown(
            f"<span style='font-size:11px;color:#8892b0;'>User: {user_id}</span>",
            unsafe_allow_html=True,
        )
    else:
        st.warning("No user found. Connect to Polar below.")

    # --- Sync & auth section ------------------------------------------------
    st.markdown("---")

    # Last sync timestamp
    _sync_info = get_last_sync_info()
    if _sync_info and _sync_info.get("synced_at"):
        from datetime import datetime as _dt
        _synced_at = _dt.fromisoformat(_sync_info["synced_at"]).astimezone()
        _today = date.today()
        _label = (
            _synced_at.strftime("Today at %H:%M")
            if _synced_at.date() == _today
            else _synced_at.strftime("%b %d at %H:%M")
        )
        st.markdown(
            f"<span style='font-size:11px;color:#8892b0;'>Last sync: "
            f"<b style='color:#c0c8d8;'>{_label}</b></span>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<span style='font-size:11px;color:#8892b0;'>Last sync: "
            "<b style='color:#c0c8d8;'>never</b></span>",
            unsafe_allow_html=True,
        )

    if is_token_available():
        # --- Sync button ---
        if st.button("Sync data", use_container_width=True, key="sidebar_sync_btn"):
            with st.status("Syncing with Polar…", expanded=True) as _status:
                try:
                    _result = run_full_sync(progress_callback=st.write)
                    _errs = _result["errors"]
                    _status.update(
                        label=(
                            f"Sync complete — {_result['exercises']} workouts, "
                            f"{_result['sleep_nights']} nights"
                            + (f" ({_errs} error{'s' if _errs != 1 else ''})" if _errs else "")
                        ),
                        state="complete" if not _errs else "error",
                    )
                except Exception as _exc:
                    _status.update(label=f"Sync failed: {_exc}", state="error")
                    st.exception(_exc)
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()
    else:
        # --- Polar auth flow ---
        with st.expander("Connect to Polar"):
            try:
                _auth_url = get_auth_url()
                st.markdown(
                    f"**Step 1.** [Open Polar authorization]({_auth_url}) in your browser and grant access.",
                    unsafe_allow_html=False,
                )
                st.caption(
                    "After granting access your browser is redirected to a local URL. "
                    "Copy the full URL from the address bar and paste it below "
                    "(even if the page shows an error — the code is in the URL)."
                )
                _callback = st.text_input(
                    "Redirect URL",
                    placeholder="http://localhost:8000/auth/polar/callback?code=…",
                    key="polar_callback_url",
                )
                if st.button("Connect", key="polar_connect_btn", use_container_width=True):
                    if _callback.strip():
                        from urllib.parse import parse_qs, urlparse as _urlparse
                        _parsed = _urlparse(_callback.strip())
                        _params = parse_qs(_parsed.query)
                        _code = (_params.get("code", [_callback.strip()])[0]).strip()
                        if _code:
                            with st.spinner("Exchanging authorization code…"):
                                try:
                                    _uid = exchange_auth_code(_code)
                                    st.success(f"Connected! Polar user {_uid}.")
                                    st.cache_data.clear()
                                    st.cache_resource.clear()
                                    st.rerun()
                                except Exception as _exc:
                                    st.error(f"Authorization failed: {_exc}")
                        else:
                            st.warning("Could not extract a code from that URL.")
                    else:
                        st.warning("Paste the redirect URL first.")
            except RuntimeError as _exc:
                st.error(str(_exc))

    if st.button("Clear cache", use_container_width=True, key="clear_cache_btn"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("Cache cleared")

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

if user_id is None:
    if is_token_available():
        st.info(
            "No data in the database yet. "
            "Use **Sync data** in the sidebar to pull your Polar data."
        )
    else:
        st.info(
            "No Polar account connected. "
            "Use **Connect to Polar** in the sidebar to authorize and sync your data."
        )
    st.stop()

if page == "Overview":
    overview.render(user_id)
elif page == "Sleep":
    sleep.render(user_id, start_date, end_date)
elif page == "Strain":
    strain.render(user_id, start_date, end_date)
elif page == "Recovery":
    recovery.render(user_id, start_date, end_date)
elif page == "Metrics Guide":
    metrics_guide.render()
