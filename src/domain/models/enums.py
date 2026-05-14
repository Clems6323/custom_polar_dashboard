"""Controlled vocabularies for domain entities.

All enums use StrEnum (Python 3.11+) so values serialise as plain strings
without extra unwrapping — convenient for JSON storage and MCP outputs.
"""

from __future__ import annotations

from enum import StrEnum


class Provider(StrEnum):
    """Canonical wearable data provider names."""

    POLAR = "polar"
    GARMIN = "garmin"
    OURA = "oura"
    APPLE = "apple"
    FITBIT = "fitbit"
    DEMO = "demo"  # synthetic data generated for demo / testing


class SportType(StrEnum):
    """Provider-agnostic activity categories.

    Ingestion adapters are responsible for mapping provider-specific sport
    labels to this enum.  Unknown or unsupported types map to OTHER.
    """

    RUNNING = "running"
    TRAIL_RUNNING = "trail_running"
    CYCLING = "cycling"
    INDOOR_CYCLING = "indoor_cycling"
    SWIMMING = "swimming"
    STRENGTH_TRAINING = "strength_training"
    HIIT = "hiit"
    YOGA = "yoga"
    WALKING = "walking"
    HIKING = "hiking"
    ROWING = "rowing"
    CROSSFIT = "crossfit"
    SOCCER = "soccer"
    TENNIS = "tennis"
    BASKETBALL = "basketball"
    OTHER = "other"


class SleepStage(StrEnum):
    """Sleep architecture stage labels."""

    AWAKE = "awake"
    LIGHT = "light"
    DEEP = "deep"
    REM = "rem"
    UNKNOWN = "unknown"
