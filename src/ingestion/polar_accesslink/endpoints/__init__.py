"""Polar AccessLink API endpoint wrappers."""

from ingestion.polar_accesslink.endpoints.activities import ActivityEndpoint
from ingestion.polar_accesslink.endpoints.cardio_load import CardioLoadEndpoint
from ingestion.polar_accesslink.endpoints.exercises import ExerciseEndpoint
from ingestion.polar_accesslink.endpoints.sleep import NightlyRechargeEndpoint, SleepEndpoint

__all__ = [
    "ActivityEndpoint",
    "CardioLoadEndpoint",
    "ExerciseEndpoint",
    "NightlyRechargeEndpoint",
    "SleepEndpoint",
]
