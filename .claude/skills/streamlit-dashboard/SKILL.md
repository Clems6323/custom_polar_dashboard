---
name: streamlit-dashboard
description: Defines standards for Streamlit dashboards, reusable UI patterns, charts, navigation, and premium analytics UX.
---

# Purpose

This skill standardizes the Streamlit frontend architecture and UX quality.

The UI should feel:
- premium
- modern
- minimal
- data-dense
- performance-oriented

Inspired by:
- Whoop
- Oura
- Garmin Connect
- modern BI dashboards

---

# UI Responsibilities

The Streamlit layer is responsible ONLY for:
- rendering
- navigation
- interaction
- visualization

Never place:
- analytics logic
- scoring formulas
- ingestion logic

inside Streamlit pages.

---

# Page Structure

Use:
- sidebar navigation
- modular pages
- reusable components
- reusable chart builders

Recommended pages:
- Dashboard
- Strain
- Sleep
- Recovery
- Trends
- Settings
- Data Sources

---

# Layout Guidance

Prefer:
- cards
- grids
- tabs
- expandable detail panels
- responsive layouts

Avoid:
- giant vertical dashboards
- cluttered pages
- too many colors
- dense unreadable tables

---

# Chart Standards

Use:
- Plotly
- reusable chart factories
- consistent spacing
- consistent axis formatting

Preferred visualizations:
- rolling trends
- sparklines
- gauges
- heatmaps
- sleep timelines
- recovery trends

---

# Dark Mode Compatibility

The UI MUST:
- render well in dark mode
- use restrained contrast
- avoid hardcoded colors

Prefer theme-aware styling.

---

# Streamlit Best Practices

Use:
- session_state
- st.cache_data
- st.cache_resource
- reusable component functions

Avoid:
- repeated expensive computations
- duplicated chart logic
- massive single-page files

---

# Performance Rules

Optimize for:
- large time-series datasets
- incremental rendering
- lazy loading
- cached aggregations

Never recompute analytics in render loops.

---

# Component Rules

Prefer:
- reusable metric cards
- typed chart configuration
- small page modules

Avoid:
- deeply nested layout code
- inline analytics
- duplicated UI patterns

---

# Navigation Guidance

Recommended sidebar structure:

- Overview
- Strain
- Sleep
- Recovery
- Trends
- Data Import
- Device Status
- Settings

---

# UX Priorities

Priority order:
1. Clarity
2. Readability
3. Navigation simplicity
4. Performance
5. Visual polish

---

# Code Generation Rules

When generating Streamlit code:
- keep pages modular
- separate charts from layout
- separate services from rendering
- keep callbacks explicit
- avoid hidden state

Always preserve UI/business-logic separation.