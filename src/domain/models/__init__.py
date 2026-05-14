"""Canonical domain models — re-exported for convenient single-import access.

Usage:
    from domain.models import ActivitySession, SleepSession, RecoveryMetrics
"""

from domain.models.activity import ActivitySession
from domain.models.base import BaseEntity, BaseTimeSeriesSample
from domain.models.enums import Provider, SleepStage, SportType
from domain.models.heart_rate import HeartRateSample
from domain.models.ppi import PPISample
from domain.models.recovery import RecoveryContributors, RecoveryMetrics
from domain.models.sleep import SleepSession, SleepStageInterval
from domain.models.sleep_metrics import SleepMetrics
from domain.models.strain import StrainMetrics
from domain.models.temperature import TemperatureSample

__all__ = [
    # Base
    "BaseEntity",
    "BaseTimeSeriesSample",
    # Enums
    "Provider",
    "SleepStage",
    "SportType",
    # Session entities
    "ActivitySession",
    "SleepSession",
    "SleepStageInterval",
    # Time-series samples
    "HeartRateSample",
    "PPISample",
    "TemperatureSample",
    # Aggregated metrics
    "RecoveryContributors",
    "RecoveryMetrics",
    "StrainMetrics",
    "SleepMetrics",
]
