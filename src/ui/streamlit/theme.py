"""Shared color palette and Plotly layout defaults for the dashboard.

All chart-producing functions should import ``PLOTLY_LAYOUT`` and spread it
into their ``layout`` kwargs so the look is consistent across pages.
"""

from __future__ import annotations

# --- Score colours ---------------------------------------------------------
# Recovery / Sleep: higher = better (green 67+, orange 34-66, red 0-33)
# Strain: higher = more stress (red 67+, orange 34-66, blue/green 0-33)

GREEN = "#00c9a7"
ORANGE = "#ffa73b"
RED = "#ff6b6b"
BLUE = "#4facfe"
PURPLE = "#b57bee"
MUTED = "#8892b0"
SURFACE = "#1a1d29"
BORDER = "#2d3142"


def score_color(score: float, *, invert: bool = False) -> str:
    """Return a traffic-light colour for a 0-100 score.

    ``invert=True`` is used for strain, where high = bad.
    """
    if invert:
        if score >= 67:
            return RED
        if score >= 34:
            return ORANGE
        return GREEN
    else:
        if score >= 67:
            return GREEN
        if score >= 34:
            return ORANGE
        return RED


def score_label(score: float, *, invert: bool = False) -> str:
    """Return a human-readable label for a 0-100 score."""
    if invert:
        if score >= 67:
            return "High"
        if score >= 34:
            return "Moderate"
        return "Low"
    else:
        if score >= 67:
            return "Optimal" if score >= 80 else "Good"
        if score >= 34:
            return "Fair"
        return "Poor"


# --- Plotly defaults --------------------------------------------------------

_AXIS_DEFAULTS: dict = {
    "gridcolor": BORDER,
    "gridwidth": 1,
    "showgrid": True,
    "zeroline": False,
    "tickfont": {"size": 11, "color": MUTED},
}

# Base layout without axis keys — charts pass axis kwargs separately
PLOTLY_LAYOUT: dict = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"color": "#e0e0e0", "family": "Inter, sans-serif", "size": 13},
    "margin": {"l": 40, "r": 20, "t": 30, "b": 40},
    "hovermode": "x unified",
    "legend": {
        "bgcolor": "rgba(0,0,0,0)",
        "bordercolor": BORDER,
        "font": {"size": 12},
    },
}


def axis(**overrides: object) -> dict:
    """Return axis config dict merging defaults with caller overrides."""
    return {**_AXIS_DEFAULTS, **overrides}

SLEEP_STAGE_COLORS = {
    "DEEP": "#4facfe",
    "REM": PURPLE,
    "LIGHT": MUTED,
    "AWAKE": "#ff6b6b",
}
