"""Metrics Guide page — renders the markdown documentation files."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

_DOCS_DIR = Path(__file__).resolve().parents[4] / "docs"

_PAGES = {
    "Sleep": _DOCS_DIR / "metrics_sleep.md",
    "Strain": _DOCS_DIR / "metrics_strain.md",
    "Recovery": _DOCS_DIR / "metrics_recovery.md",
}


def render() -> None:
    st.markdown("## Metrics Guide")
    st.caption(
        "Detailed documentation: input data, scoring formulas, and physiological rationale "
        "for every metric computed by the Polar Dashboard."
    )
    st.markdown("---")

    tab_sleep, tab_strain, tab_recovery = st.tabs(["Sleep", "Strain", "Recovery"])

    for tab, (name, path) in zip(
        [tab_sleep, tab_strain, tab_recovery], _PAGES.items()
    ):
        with tab:
            if path.exists():
                st.markdown(path.read_text(encoding="utf-8"))
            else:
                st.error(f"Documentation file not found: {path}")
