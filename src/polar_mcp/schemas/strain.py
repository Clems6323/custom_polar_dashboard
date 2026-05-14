"""MCP output schemas for strain and training load tools."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from domain.models.strain import StrainMetrics
from polar_mcp.schemas.common import ToolMeta


def _strain_confidence(m: StrainMetrics) -> tuple[float, list[str]]:
    optional_fields = [
        ("muscle_load", m.muscle_load),
        ("acute_load", m.acute_load),
        ("chronic_load", m.chronic_load),
        ("acwr", m.acwr),
    ]
    missing = [name for name, val in optional_fields if val is None]
    confidence = (len(optional_fields) - len(missing)) / len(optional_fields)
    return round(confidence, 3), missing


class ACWRZone(BaseModel):
    """ACWR interpretation based on Gabbett 2016 sports science literature."""

    value: float
    zone: str = Field(description="under_training | sweet_spot | caution | elevated_risk")
    description: str

    @classmethod
    def from_value(cls, acwr: float) -> ACWRZone:
        if acwr < 0.8:
            return cls(
                value=acwr,
                zone="under_training",
                description="Acute load well below chronic baseline; consider progressive overload",
            )
        if acwr <= 1.3:
            return cls(
                value=acwr,
                zone="sweet_spot",
                description="Optimal acute/chronic balance (0.8-1.3); low injury risk",
            )
        if acwr <= 1.5:
            return cls(
                value=acwr,
                zone="caution",
                description="Load spike approaching risk threshold; monitor closely",
            )
        return cls(
            value=acwr,
            zone="elevated_risk",
            description="ACWR > 1.5: elevated soft-tissue injury risk (Gabbett 2016)",
        )


class StrainScoreOutput(BaseModel):
    """Daily training strain for a single date."""

    record_date: date
    user_id: str
    provider: str

    strain_score: float = Field(
        ge=0,
        le=100,
        description="Normalised strain score (0-100); 0-33 low, 34-66 moderate, 67-100 high",
    )
    cardio_load: float = Field(
        ge=0,
        description="Polar Cardio Load for the day (sum across sessions)",
    )
    muscle_load: float | None = Field(
        default=None,
        description="Movement-derived musculoskeletal load component",
    )
    acute_load: float | None = Field(
        default=None,
        description="7-day rolling average training load",
    )
    chronic_load: float | None = Field(
        default=None,
        description="28-day rolling average training load",
    )
    acwr_analysis: ACWRZone | None = Field(
        default=None,
        description="ACWR value with injury-risk zone classification",
    )
    session_count: int = Field(ge=0, description="Number of sessions contributing to today's load")
    session_ids: list[str] = Field(default_factory=list)

    metadata: ToolMeta

    @classmethod
    def from_domain(cls, m: StrainMetrics) -> StrainScoreOutput:
        confidence, missing = _strain_confidence(m)
        return cls(
            record_date=m.record_date,
            user_id=m.user_id,
            provider=str(m.provider),
            strain_score=m.strain_score,
            cardio_load=m.cardio_load,
            muscle_load=m.muscle_load,
            acute_load=m.acute_load,
            chronic_load=m.chronic_load,
            acwr_analysis=(ACWRZone.from_value(m.acwr) if m.acwr is not None else None),
            session_count=m.session_count,
            session_ids=m.session_ids,
            metadata=ToolMeta(
                data_available=True,
                confidence=confidence,
                missing_signals=missing,
            ),
        )


class TrainingLoadPoint(BaseModel):
    """Single-day cardio load data point within a load history response."""

    record_date: date
    cardio_load: float
    strain_score: float
    acwr: float | None = None
    session_count: int = 0


class TrainingLoadSummary(BaseModel):
    days_with_data: int
    total_load: float = Field(description="Sum of daily cardio loads over the window")
    avg_daily_load: float | None = None
    avg_strain_score: float | None = None
    peak_load: float | None = None
    peak_load_date: date | None = None
    latest_acwr: float | None = Field(
        default=None,
        description="Most recent ACWR value in the requested window",
    )


class TrainingLoadOutput(BaseModel):
    """Training load time-series for a date range."""

    user_id: str
    start_date: date
    end_date: date
    data: list[TrainingLoadPoint]
    summary: TrainingLoadSummary
    metadata: ToolMeta

    @classmethod
    def from_domain(
        cls,
        user_id: str,
        start: date,
        end: date,
        records: list[StrainMetrics],
    ) -> TrainingLoadOutput:
        points = [
            TrainingLoadPoint(
                record_date=r.record_date,
                cardio_load=r.cardio_load,
                strain_score=r.strain_score,
                acwr=r.acwr,
                session_count=r.session_count,
            )
            for r in records
        ]

        loads = [r.cardio_load for r in records]
        strains = [r.strain_score for r in records]
        acwrs = [r.acwr for r in records if r.acwr is not None]

        peak_record = max(records, key=lambda r: r.cardio_load) if records else None

        summary = TrainingLoadSummary(
            days_with_data=len(records),
            total_load=round(sum(loads), 2),
            avg_daily_load=round(sum(loads) / len(loads), 2) if loads else None,
            avg_strain_score=round(sum(strains) / len(strains), 2) if strains else None,
            peak_load=round(peak_record.cardio_load, 2) if peak_record else None,
            peak_load_date=peak_record.record_date if peak_record else None,
            latest_acwr=acwrs[-1] if acwrs else None,
        )

        confidence = len(records) / max((end - start).days + 1, 1)
        return cls(
            user_id=user_id,
            start_date=start,
            end_date=end,
            data=points,
            summary=summary,
            metadata=ToolMeta(
                data_available=len(records) > 0,
                confidence=round(min(confidence, 1.0), 3),
                missing_signals=([] if records else ["no_records_in_range"]),
            ),
        )
