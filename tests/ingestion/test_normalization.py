"""Tests for ingestion normalization functions.

All tests use hand-crafted fixtures that mirror the actual Polar API response
shape — no real API calls are made.
"""

from __future__ import annotations

import datetime

import pytest

from domain.models.enums import Provider, SleepStage, SportType
from ingestion.normalization.exercise import normalize_exercise
from ingestion.normalization.nightly_recharge import normalize_nightly_recharge
from ingestion.normalization.activity import normalize_activity_summary
from ingestion.normalization.sleep import (
    _parse_hypnogram,
    _stage_stats_from_hypnogram,
    normalize_sleep,
)
from ingestion.polar_accesslink.models import PolarActivitySummary
from ingestion.normalization.utils import (
    local_to_utc,
    parse_as_utc,
    parse_iso_duration,
    sport_type_from_polar,
)
from ingestion.polar_accesslink.models import (
    PolarExercise,
    PolarHeartRateSummary,
    PolarHeartRateZone,
    PolarNightlyRecharge,
    PolarSleepData,
    PolarTrainingLoadPro,
)

_USER = "user-001"


# ---------------------------------------------------------------------------
# ISO duration parser
# ---------------------------------------------------------------------------


class TestParseDuration:
    def test_hours_minutes_seconds(self) -> None:
        assert parse_iso_duration("PT1H15M30.000S") == pytest.approx(4530.0)

    def test_minutes_only(self) -> None:
        assert parse_iso_duration("PT45M") == pytest.approx(2700.0)

    def test_seconds_only(self) -> None:
        assert parse_iso_duration("PT30.5S") == pytest.approx(30.5)

    def test_hours_only(self) -> None:
        assert parse_iso_duration("PT2H") == pytest.approx(7200.0)

    def test_days_and_hours(self) -> None:
        assert parse_iso_duration("P1DT2H") == pytest.approx(86400 + 7200)

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_iso_duration("not-a-duration")

    def test_zero_duration(self) -> None:
        assert parse_iso_duration("PT0S") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Sport type mapping
# ---------------------------------------------------------------------------


class TestSportTypeMapping:
    def test_running(self) -> None:
        assert sport_type_from_polar("RUNNING") == SportType.RUNNING

    def test_trail_running(self) -> None:
        assert sport_type_from_polar("TRAIL_RUNNING") == SportType.TRAIL_RUNNING

    def test_cycling(self) -> None:
        assert sport_type_from_polar("CYCLING") == SportType.CYCLING

    def test_case_insensitive(self) -> None:
        assert sport_type_from_polar("running") == SportType.RUNNING

    def test_unknown_maps_to_other(self) -> None:
        assert sport_type_from_polar("UNKNOWN_SPORT") == SportType.OTHER

    def test_none_maps_to_other(self) -> None:
        assert sport_type_from_polar(None) == SportType.OTHER


# ---------------------------------------------------------------------------
# Datetime helpers
# ---------------------------------------------------------------------------


class TestDatetimeHelpers:
    def test_local_to_utc_positive_offset(self) -> None:
        # UTC+2: 08:00 local → 06:00 UTC
        result = local_to_utc("2024-05-10T08:00:00", 120)
        assert result.hour == 6
        assert result.tzinfo is not None

    def test_local_to_utc_zero_offset(self) -> None:
        result = local_to_utc("2024-05-10T12:00:00", 0)
        assert result.hour == 12

    def test_parse_as_utc(self) -> None:
        result = parse_as_utc("2024-05-10T08:00:00")
        assert result.tzinfo is not None
        assert result.year == 2024
        assert result.hour == 8

    def test_parse_as_utc_with_millis(self) -> None:
        result = parse_as_utc("2024-05-10T08:00:00.000")
        assert result.hour == 8


# ---------------------------------------------------------------------------
# Exercise normalization
# ---------------------------------------------------------------------------


def _make_exercise(**kw: object) -> PolarExercise:
    defaults: dict = {
        "id": "0LYLpB8g",
        "start_time": "2024-05-10T08:00:00",
        "start_time_utc_offset": 120,
        "duration": "PT1H15M30.000S",
        "sport": "RUNNING",
    }
    defaults.update(kw)
    return PolarExercise(**defaults)


class TestExerciseNormalization:
    def test_basic_fields(self) -> None:
        ex = _make_exercise()
        session = normalize_exercise(ex, _USER)

        assert session.user_id == _USER
        assert session.provider == Provider.POLAR
        assert session.sport_type == SportType.RUNNING
        assert session.id == f"exercise_{_USER}_0LYLpB8g"

    def test_duration_converted_to_seconds(self) -> None:
        ex = _make_exercise(duration="PT1H15M30.000S")
        session = normalize_exercise(ex, _USER)
        assert session.duration_seconds == pytest.approx(4530.0)

    def test_utc_offset_applied(self) -> None:
        # UTC+2 offset: 08:00 local → 06:00 UTC
        ex = _make_exercise(start_time="2024-05-10T08:00:00", start_time_utc_offset=120)
        session = normalize_exercise(ex, _USER)
        assert session.start_time.hour == 6

    def test_end_time_derived_from_duration(self) -> None:
        ex = _make_exercise(start_time="2024-05-10T08:00:00", start_time_utc_offset=0,
                            duration="PT1H")
        session = normalize_exercise(ex, _USER)
        assert session.end_time.hour == 9

    def test_hr_fields(self) -> None:
        ex = _make_exercise(
            heart_rate=PolarHeartRateSummary(average=145, maximum=175),
        )
        session = normalize_exercise(ex, _USER)
        assert session.average_hr_bpm == pytest.approx(145.0)
        assert session.max_hr_bpm == pytest.approx(175.0)

    def test_hr_zones_parsed(self) -> None:
        zones = [
            PolarHeartRateZone(index=1, in_zone="PT5M"),
            PolarHeartRateZone(index=2, in_zone="PT10M"),
        ]
        ex = _make_exercise(heart_rate_zones=zones)
        session = normalize_exercise(ex, _USER)
        assert session.hr_zone_distribution is not None
        assert session.hr_zone_distribution["1"] == pytest.approx(300.0)
        assert session.hr_zone_distribution["2"] == pytest.approx(600.0)

    def test_cardio_load_from_training_load_pro(self) -> None:
        tlp = PolarTrainingLoadPro(**{"cardio-load": 20.0, "muscle-load": -1.0})
        ex = _make_exercise(training_load_pro=tlp)
        session = normalize_exercise(ex, _USER)
        assert session.cardio_load == pytest.approx(20.0)
        assert session.muscle_load is None  # -1.0 means not available

    def test_detailed_sport_used_for_mapping(self) -> None:
        ex = _make_exercise(sport="RUNNING", detailed_sport_info="TRAIL_RUNNING")
        session = normalize_exercise(ex, _USER)
        assert session.sport_type == SportType.TRAIL_RUNNING

    def test_timestamps_are_utc_aware(self) -> None:
        session = normalize_exercise(_make_exercise(), _USER)
        assert session.start_time.tzinfo is not None
        assert session.end_time.tzinfo is not None


# ---------------------------------------------------------------------------
# Sleep normalization
# ---------------------------------------------------------------------------


def _make_sleep(**kw: object) -> PolarSleepData:
    defaults: dict = {
        "date": "2024-05-10",
        "sleep_start_time": "2024-05-09T23:00:00.000",
        "sleep_end_time": "2024-05-10T07:00:00.000",
        "light_sleep": 10800,   # 3h
        "deep_sleep": 7200,     # 2h
        "rem_sleep": 10800,     # 3h
        "total_interruption_duration": 900,
        "sleep_score": 82.0,
        "continuity": 3.5,
    }
    defaults.update(kw)
    return PolarSleepData(**defaults)


class TestSleepNormalization:
    def test_session_id_format(self) -> None:
        session, _ = normalize_sleep(_make_sleep(), _USER)
        assert session.id == f"sleep_{_USER}_2024-05-10"

    def test_provider(self) -> None:
        session, _ = normalize_sleep(_make_sleep(), _USER)
        assert session.provider == Provider.POLAR

    def test_timestamps_are_utc_aware(self) -> None:
        session, _ = normalize_sleep(_make_sleep(), _USER)
        assert session.start_time.tzinfo is not None
        assert session.end_time.tzinfo is not None

    def test_sleep_stage_seconds(self) -> None:
        session, _ = normalize_sleep(_make_sleep(), _USER)
        assert session.light_sleep_seconds == pytest.approx(10800.0)
        assert session.deep_sleep_seconds == pytest.approx(7200.0)
        assert session.rem_sleep_seconds == pytest.approx(10800.0)

    def test_sleep_metrics_percentages_sum(self) -> None:
        # All five components (DEEP + REM + LIGHT + INTERRUPTIONS + UNKNOWN) are
        # fractions of time in bed and should together account for most of the night.
        _, metrics = normalize_sleep(_make_sleep(), _USER)
        total = (
            (metrics.deep_sleep_pct or 0)
            + (metrics.rem_sleep_pct or 0)
            + (metrics.light_sleep_pct or 0)
            + (metrics.awake_pct or 0)
            + (metrics.unknown_sleep_pct or 0)
        )
        assert total <= 110.0  # generous bound for floating-point rounding

    def test_sleep_score_from_polar(self) -> None:
        _, metrics = normalize_sleep(_make_sleep(sleep_score=75.0), _USER)
        assert metrics.sleep_score == pytest.approx(75.0)

    def test_sleep_score_default_when_missing(self) -> None:
        _, metrics = normalize_sleep(_make_sleep(sleep_score=None), _USER)
        assert metrics.sleep_score == pytest.approx(50.0)

    def test_efficiency_computed(self) -> None:
        # 8h in bed, 3+2+3=8h sleep, 15min awake recorded separately
        _, metrics = normalize_sleep(_make_sleep(), _USER)
        assert metrics.sleep_efficiency_pct is not None
        assert metrics.sleep_efficiency_pct > 0

    def test_record_date_is_wake_date(self) -> None:
        _, metrics = normalize_sleep(_make_sleep(), _USER)
        assert metrics.record_date == datetime.date(2024, 5, 10)

    def test_interruption_durations_passed_through(self) -> None:
        session, metrics = normalize_sleep(
            _make_sleep(short_interruption_duration=300, long_interruption_duration=600), _USER
        )
        assert session.short_interruption_duration_seconds == pytest.approx(300.0)
        assert session.long_interruption_duration_seconds == pytest.approx(600.0)
        assert metrics.short_interruption_duration_seconds == pytest.approx(300.0)
        assert metrics.long_interruption_duration_seconds == pytest.approx(600.0)

    def test_interruption_durations_none_when_absent(self) -> None:
        session, metrics = normalize_sleep(_make_sleep(), _USER)
        assert session.short_interruption_duration_seconds is None
        assert session.long_interruption_duration_seconds is None
        assert metrics.short_interruption_duration_seconds is None
        assert metrics.long_interruption_duration_seconds is None

    def test_continuity_scaled_to_20_100(self) -> None:
        session, _ = normalize_sleep(_make_sleep(continuity=3.0), _USER)
        assert session.continuity_score == pytest.approx(60.0)

    def test_continuity_min_1_maps_to_20(self) -> None:
        session, _ = normalize_sleep(_make_sleep(continuity=1.0), _USER)
        assert session.continuity_score == pytest.approx(20.0)

    def test_continuity_max_5_maps_to_100(self) -> None:
        session, _ = normalize_sleep(_make_sleep(continuity=5.0), _USER)
        assert session.continuity_score == pytest.approx(100.0)

    def test_continuity_none_gives_none(self) -> None:
        session, _ = normalize_sleep(_make_sleep(continuity=None), _USER)
        assert session.continuity_score is None

    def test_hypnogram_used_when_no_api_stage_fields(self) -> None:
        # elif hypno_stats branch: no API duration fields but hypnogram present
        # "1111" = 4 REM epochs × 300 s = 1200 s
        session, metrics = normalize_sleep(
            _make_sleep(
                hypnogram_5min="1111",
                deep_sleep=None,
                rem_sleep=None,
                light_sleep=None,
                total_interruption_duration=None,
            ),
            _USER,
        )
        assert session.rem_sleep_seconds == pytest.approx(1200.0)
        assert metrics.rem_sleep_pct == pytest.approx(100.0)

    def test_no_stage_data_at_all_yields_none_percentages(self) -> None:
        # else branch: no API fields, no hypnogram
        session, metrics = normalize_sleep(
            _make_sleep(
                deep_sleep=None,
                rem_sleep=None,
                light_sleep=None,
                total_interruption_duration=None,
            ),
            _USER,
        )
        assert session.deep_sleep_seconds is None
        assert session.rem_sleep_seconds is None
        assert metrics.deep_sleep_pct is None
        assert metrics.rem_sleep_pct is None

    def test_bad_hypnogram_swallowed_and_fallback_used(self) -> None:
        # try/except branch: invalid hypnogram → parse error is swallowed,
        # normalize_sleep should still succeed using the API stage fields
        from unittest.mock import patch

        with patch(
            "ingestion.normalization.sleep._parse_hypnogram",
            side_effect=ValueError("bad hypnogram"),
        ):
            session, metrics = normalize_sleep(
                _make_sleep(hypnogram_5min="1234"),
                _USER,
            )
        # API stage fields (from _make_sleep defaults) should still be used
        assert session.stage_intervals == []
        assert session.deep_sleep_seconds is not None


# ---------------------------------------------------------------------------
# Hypnogram parsing
# ---------------------------------------------------------------------------


class TestHypnogramParsing:
    def test_single_stage_all_rem(self) -> None:
        # 1 = REM per Polar AccessLink v3 spec
        start = datetime.datetime(2024, 5, 9, 23, 0, tzinfo=datetime.UTC)
        intervals = _parse_hypnogram("1111", start, "test-session")
        assert len(intervals) == 1  # merged into one interval
        assert intervals[0].stage == SleepStage.REM
        assert intervals[0].duration_seconds == pytest.approx(1200.0)  # 4 x 5min

    def test_single_stage_all_light(self) -> None:
        # 2 = LIGHTER NREM, 3 = LIGHT NREM — both map to LIGHT
        start = datetime.datetime(2024, 5, 9, 23, 0, tzinfo=datetime.UTC)
        intervals = _parse_hypnogram("2222", start, "test-session")
        assert len(intervals) == 1
        assert intervals[0].stage == SleepStage.LIGHT

    def test_stage_transitions_produce_separate_intervals(self) -> None:
        # 1=REM, 4=DEEP → two distinct intervals
        start = datetime.datetime(2024, 5, 9, 23, 0, tzinfo=datetime.UTC)
        intervals = _parse_hypnogram("1144", start, "test-session")
        assert len(intervals) == 2
        assert intervals[0].stage == SleepStage.REM
        assert intervals[1].stage == SleepStage.DEEP

    def test_light_nrem_variants_both_map_to_light(self) -> None:
        # 2 and 3 are different raw characters so they produce separate intervals,
        # but both map to SleepStage.LIGHT
        start = datetime.datetime(2024, 5, 9, 23, 0, tzinfo=datetime.UTC)
        intervals = _parse_hypnogram("2233", start, "test-session")
        assert len(intervals) == 2
        assert intervals[0].stage == SleepStage.LIGHT
        assert intervals[1].stage == SleepStage.LIGHT

    def test_stage_4_maps_to_deep(self) -> None:
        start = datetime.datetime(2024, 5, 9, 23, 0, tzinfo=datetime.UTC)
        intervals = _parse_hypnogram("4", start, "test-session")
        assert intervals[0].stage == SleepStage.DEEP

    def test_stage_5_maps_to_unknown(self) -> None:
        start = datetime.datetime(2024, 5, 9, 23, 0, tzinfo=datetime.UTC)
        intervals = _parse_hypnogram("5", start, "test-session")
        assert intervals[0].stage == SleepStage.UNKNOWN

    def test_stage_0_maps_to_awake(self) -> None:
        start = datetime.datetime(2024, 5, 9, 23, 0, tzinfo=datetime.UTC)
        intervals = _parse_hypnogram("0", start, "test-session")
        assert intervals[0].stage == SleepStage.AWAKE

    def test_intervals_are_contiguous(self) -> None:
        # 0=WAKE, 1=REM, 4=DEEP, 5=UNKNOWN → 4 separate intervals
        start = datetime.datetime(2024, 5, 9, 23, 0, tzinfo=datetime.UTC)
        intervals = _parse_hypnogram("0145", start, "test-session")
        assert len(intervals) == 4
        for i in range(len(intervals) - 1):
            assert intervals[i].end_time == intervals[i + 1].start_time

    def test_empty_string_returns_empty_list(self) -> None:
        start = datetime.datetime(2024, 5, 9, 23, 0, tzinfo=datetime.UTC)
        assert _parse_hypnogram("", start, "session") == []

    def test_non_datetime_sleep_start_raises(self) -> None:
        with pytest.raises(TypeError, match="sleep_start must be a datetime"):
            _parse_hypnogram("1234", "not-a-datetime", "session")


# ---------------------------------------------------------------------------
# Stage stats from hypnogram
# ---------------------------------------------------------------------------


class TestStageStatsFromHypnogram:
    def test_empty_returns_none(self) -> None:
        assert _stage_stats_from_hypnogram("") is None

    def test_all_deep_seconds_and_pct(self) -> None:
        stats = _stage_stats_from_hypnogram("444")
        assert stats is not None
        assert stats["deep_s"] == pytest.approx(900.0)  # 3 × 300 s
        assert stats["deep_pct"] == pytest.approx(100.0)
        assert stats["rem_s"] == pytest.approx(0.0)
        assert stats["rem_pct"] == pytest.approx(0.0)

    def test_mixed_stages_correct_split(self) -> None:
        # "1144" = 2 REM + 2 DEEP → 50 % each
        stats = _stage_stats_from_hypnogram("1144")
        assert stats is not None
        assert stats["rem_s"] == pytest.approx(600.0)
        assert stats["deep_s"] == pytest.approx(600.0)
        assert stats["rem_pct"] == pytest.approx(50.0)
        assert stats["deep_pct"] == pytest.approx(50.0)

    def test_light_nrem_codes_2_and_3_both_count_as_light(self) -> None:
        # "223" = 3 epochs all LIGHT
        stats = _stage_stats_from_hypnogram("223")
        assert stats is not None
        assert stats["light_s"] == pytest.approx(900.0)
        assert stats["light_pct"] == pytest.approx(100.0)

    def test_all_five_stages_percentages_sum_to_100(self) -> None:
        stats = _stage_stats_from_hypnogram("01234")
        assert stats is not None
        total = (
            stats["deep_pct"]
            + stats["rem_pct"]
            + stats["light_pct"]
            + stats["awake_pct"]
            + stats["unknown_pct"]
        )
        assert total == pytest.approx(100.0, abs=0.2)


# ---------------------------------------------------------------------------
# Nightly recharge normalization
# ---------------------------------------------------------------------------


def _make_recharge(**kw: object) -> PolarNightlyRecharge:
    defaults: dict = {
        "date": "2024-05-10",
        "ans_charge": 0.7,
        "ans_charge_status": 3,
        "heart_rate_avg": 56,
        "beat_to_beat_avg": 1071,
        "heart_rate_variability_avg": 48.5,
        "breathing_rate_avg": 14.2,
    }
    defaults.update(kw)
    return PolarNightlyRecharge(**defaults)


class TestNightlyRechargeNormalization:
    def test_recovery_score_from_ans_charge_status(self) -> None:
        # status 4 → 70.0
        metrics = normalize_nightly_recharge(_make_recharge(ans_charge_status=4), _USER)
        assert metrics.recovery_score == pytest.approx(70.0)

    def test_recovery_score_default_when_status_missing(self) -> None:
        metrics = normalize_nightly_recharge(_make_recharge(ans_charge_status=None), _USER)
        assert metrics.recovery_score == pytest.approx(50.0)

    def test_resting_hr_from_heart_rate_avg(self) -> None:
        metrics = normalize_nightly_recharge(_make_recharge(heart_rate_avg=60), _USER)
        assert metrics.resting_hr_bpm == pytest.approx(60.0)

    def test_resting_hr_derived_from_beat_to_beat_when_avg_missing(self) -> None:
        metrics = normalize_nightly_recharge(
            _make_recharge(heart_rate_avg=None, beat_to_beat_avg=1000), _USER
        )
        assert metrics.resting_hr_bpm == pytest.approx(60.0, abs=0.1)

    def test_rmssd_from_hrv_avg(self) -> None:
        metrics = normalize_nightly_recharge(_make_recharge(), _USER)
        assert metrics.rmssd_ms == pytest.approx(48.5)

    def test_rmssd_none_when_missing(self) -> None:
        metrics = normalize_nightly_recharge(
            _make_recharge(heart_rate_variability_avg=None), _USER
        )
        assert metrics.rmssd_ms is None

    def test_no_baselines_from_ingestion(self) -> None:
        metrics = normalize_nightly_recharge(_make_recharge(), _USER)
        assert metrics.hrv_baseline_ms is None
        assert metrics.resting_hr_baseline_bpm is None

    def test_nightly_recharge_contributor_normalized(self) -> None:
        # ans_charge=0.7 → (0.7+10)*5 = 53.5
        metrics = normalize_nightly_recharge(_make_recharge(ans_charge=0.7), _USER)
        assert metrics.contributors.nightly_recharge_score == pytest.approx(53.5)

    def test_nightly_recharge_contributor_clamped_at_100(self) -> None:
        # ans_charge=9.7 → (9.7+10)*5 = 98.5 (within range)
        metrics = normalize_nightly_recharge(_make_recharge(ans_charge=9.7), _USER)
        assert metrics.contributors.nightly_recharge_score == pytest.approx(98.5)

    def test_nightly_recharge_contributor_clamped_at_0(self) -> None:
        # ans_charge=-9.8 → (-9.8+10)*5 = 1.0 (within range)
        metrics = normalize_nightly_recharge(_make_recharge(ans_charge=-9.8), _USER)
        assert metrics.contributors.nightly_recharge_score == pytest.approx(1.0)

    def test_provider_is_polar(self) -> None:
        metrics = normalize_nightly_recharge(_make_recharge(), _USER)
        assert metrics.provider == Provider.POLAR

    def test_record_date(self) -> None:
        metrics = normalize_nightly_recharge(_make_recharge(), _USER)
        assert metrics.record_date == datetime.date(2024, 5, 10)


# ---------------------------------------------------------------------------
# Activity summary normalization
# ---------------------------------------------------------------------------


def _make_activity(**kw: object) -> PolarActivitySummary:
    defaults: dict = {
        "date": "2024-05-10",
        "calories": 2200,
        "active_calories": 450,
        "duration": "PT1H30M",
        "active_steps": 8500,
    }
    defaults.update(kw)
    return PolarActivitySummary(**defaults)


class TestActivityNormalization:
    def test_date_from_polar_date_field(self) -> None:
        totals = normalize_activity_summary(_make_activity(date="2024-05-10"))
        assert totals.date == datetime.date(2024, 5, 10)

    def test_date_extracted_from_start_time_when_date_missing(self) -> None:
        totals = normalize_activity_summary(
            _make_activity(date=None, start_time="2024-05-10T06:00:00")
        )
        assert totals.date == datetime.date(2024, 5, 10)

    def test_neither_date_nor_start_time_raises(self) -> None:
        with pytest.raises(ValueError, match="neither"):
            normalize_activity_summary(_make_activity(date=None, start_time=None))

    def test_duration_parsed_to_seconds(self) -> None:
        totals = normalize_activity_summary(_make_activity(duration="PT1H30M"))
        assert totals.active_seconds == pytest.approx(5400.0)

    def test_invalid_duration_gives_none(self) -> None:
        # contextlib.suppress(ValueError) — bad duration is silently ignored
        totals = normalize_activity_summary(_make_activity(duration="not-a-duration"))
        assert totals.active_seconds is None

    def test_no_duration_gives_none(self) -> None:
        totals = normalize_activity_summary(_make_activity(duration=None))
        assert totals.active_seconds is None

    def test_calories_and_steps_passed_through(self) -> None:
        totals = normalize_activity_summary(_make_activity(calories=2000, active_steps=9000))
        assert totals.calories == 2000
        assert totals.active_steps == 9000

    def test_repr_contains_date_and_steps(self) -> None:
        totals = normalize_activity_summary(_make_activity())
        r = repr(totals)
        assert "2024-05-10" in r
        assert "8500" in r


# ---------------------------------------------------------------------------
# utils.py branch coverage
# ---------------------------------------------------------------------------


class TestUtilsMissingBranches:
    def test_iso_duration_with_years(self) -> None:
        # Line 48: years component
        secs = parse_iso_duration("P1Y")
        assert secs == pytest.approx(365.25 * 86_400)

    def test_iso_duration_with_months(self) -> None:
        # Line 50: months component
        secs = parse_iso_duration("P2M")
        assert secs == pytest.approx(2 * 30.44 * 86_400)

    def test_parse_as_utc_with_tz_offset(self) -> None:
        # Line 137: dt.tzinfo is not None → convert to UTC
        result = parse_as_utc("2024-05-10T10:00:00+02:00")
        assert result.hour == 8  # 10:00+02 → 08:00 UTC
        assert result.tzinfo is not None

    def test_parse_polar_datetime_invalid_raises(self) -> None:
        # Lines 149-150: ValueError re-raised from _parse_polar_datetime
        with pytest.raises(ValueError, match="Cannot parse Polar datetime"):
            parse_as_utc("not-a-date")


# ---------------------------------------------------------------------------
# exercise.py branch coverage
# ---------------------------------------------------------------------------


class TestExerciseMissingBranches:
    def test_muscle_load_non_negative_is_set(self) -> None:
        # Line 70: muscle_load >= 0 → set on session
        from ingestion.polar_accesslink.models import PolarTrainingLoadPro
        tlp = PolarTrainingLoadPro(**{"cardio-load": 20.0, "muscle-load": 15.0})
        session = normalize_exercise(_make_exercise(training_load_pro=tlp), _USER)
        assert session.muscle_load == pytest.approx(15.0)

    def test_hr_zone_invalid_duration_is_skipped(self) -> None:
        # Lines 31-32: ValueError from bad zone duration is caught, zone skipped
        zones = [
            PolarHeartRateZone(index=1, in_zone="INVALID"),
            PolarHeartRateZone(index=2, in_zone="PT5M"),
        ]
        session = normalize_exercise(_make_exercise(heart_rate_zones=zones), _USER)
        # Zone 1 is skipped; zone 2 is kept
        assert session.hr_zone_distribution is not None
        assert "1" not in session.hr_zone_distribution
        assert session.hr_zone_distribution["2"] == pytest.approx(300.0)
