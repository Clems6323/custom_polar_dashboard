"""Abstract repository protocols for all domain entities.

Using ``typing.Protocol`` (structural subtyping) means concrete repository
classes do not need to inherit from a base class — they just need to implement
the required methods.  This keeps the domain layer dependency-free.

Dependency direction: Storage → Domain (via these protocols).
Services depend on the protocols, not on DuckDB directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Protocol

from domain.models import (
    ActivitySession,
    RecoveryMetrics,
    SleepMetrics,
    SleepSession,
    StrainMetrics,
)


class ActivityRepository(Protocol):
    """Persistence interface for ActivitySession records."""

    def upsert(self, session: ActivitySession) -> None:
        """Save or update a single session."""
        ...

    def upsert_batch(self, sessions: Sequence[ActivitySession]) -> None:
        """Save or update a collection of sessions atomically."""
        ...

    def get(self, session_id: str) -> ActivitySession | None:
        """Return the session with the given ID, or None."""
        ...

    def list_by_date_range(
        self,
        user_id: str,
        start: date,
        end: date,
    ) -> list[ActivitySession]:
        """Return sessions whose start_time falls within [start, end]."""
        ...

    def list_latest(self, user_id: str, n: int = 30) -> list[ActivitySession]:
        """Return the n most recent sessions for a user."""
        ...

    def delete(self, session_id: str) -> None:
        """Remove a session by ID (idempotent)."""
        ...


class SleepRepository(Protocol):
    """Persistence interface for SleepSession records (+ stage intervals)."""

    def upsert(self, session: SleepSession) -> None: ...
    def upsert_batch(self, sessions: Sequence[SleepSession]) -> None: ...
    def get(self, session_id: str) -> SleepSession | None: ...

    def list_by_date_range(
        self,
        user_id: str,
        start: date,
        end: date,
    ) -> list[SleepSession]: ...

    def list_latest(self, user_id: str, n: int = 30) -> list[SleepSession]: ...
    def delete(self, session_id: str) -> None: ...


class RecoveryMetricsRepository(Protocol):
    """Persistence interface for daily RecoveryMetrics."""

    def upsert(self, metrics: RecoveryMetrics) -> None: ...
    def get(self, user_id: str, record_date: date) -> RecoveryMetrics | None: ...

    def list_by_date_range(
        self,
        user_id: str,
        start: date,
        end: date,
    ) -> list[RecoveryMetrics]: ...


class StrainMetricsRepository(Protocol):
    """Persistence interface for daily StrainMetrics."""

    def upsert(self, metrics: StrainMetrics) -> None: ...
    def get(self, user_id: str, record_date: date) -> StrainMetrics | None: ...

    def list_by_date_range(
        self,
        user_id: str,
        start: date,
        end: date,
    ) -> list[StrainMetrics]: ...


class SleepMetricsRepository(Protocol):
    """Persistence interface for daily SleepMetrics."""

    def upsert(self, metrics: SleepMetrics) -> None: ...
    def get(self, user_id: str, record_date: date) -> SleepMetrics | None: ...

    def list_by_date_range(
        self,
        user_id: str,
        start: date,
        end: date,
    ) -> list[SleepMetrics]: ...
