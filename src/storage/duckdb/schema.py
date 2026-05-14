"""DuckDB DDL statements for all platform tables.

Tables are grouped by domain.  The migration runner executes each statement
in order; all use CREATE TABLE IF NOT EXISTS so they are idempotent.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Migration tracking
# ---------------------------------------------------------------------------

DDL_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS _schema_migrations (
    id         VARCHAR PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT current_timestamp
)
"""

# ---------------------------------------------------------------------------
# Session tables (one row per session)
# ---------------------------------------------------------------------------

DDL_ACTIVITY_SESSIONS = """
CREATE TABLE IF NOT EXISTS activity_sessions (
    id                       VARCHAR PRIMARY KEY,
    user_id                  VARCHAR      NOT NULL,
    provider                 VARCHAR      NOT NULL,
    start_time               TIMESTAMPTZ  NOT NULL,
    end_time                 TIMESTAMPTZ  NOT NULL,
    duration_seconds         DOUBLE       NOT NULL,
    sport_type               VARCHAR      NOT NULL DEFAULT 'other',
    sport_label              VARCHAR,
    average_hr_bpm           DOUBLE,
    max_hr_bpm               DOUBLE,
    hr_zone_distribution     JSON,
    cardio_load              DOUBLE,
    muscle_load              DOUBLE,
    perceived_exertion       DOUBLE,
    calories_kcal            DOUBLE,
    distance_meters          DOUBLE,
    average_pace_sec_per_km  DOUBLE,
    average_power_watts      DOUBLE,
    ingested_at              TIMESTAMPTZ  DEFAULT current_timestamp
)
"""

DDL_ACTIVITY_SESSIONS_IDX = """
CREATE INDEX IF NOT EXISTS idx_activity_user_time
    ON activity_sessions (user_id, start_time)
"""

DDL_SLEEP_SESSIONS = """
CREATE TABLE IF NOT EXISTS sleep_sessions (
    id                              VARCHAR PRIMARY KEY,
    user_id                         VARCHAR     NOT NULL,
    provider                        VARCHAR     NOT NULL,
    start_time                      TIMESTAMPTZ NOT NULL,
    end_time                        TIMESTAMPTZ NOT NULL,
    duration_seconds                DOUBLE      NOT NULL,
    sleep_latency_seconds           DOUBLE,
    continuity_score                DOUBLE,
    sleep_efficiency_pct            DOUBLE,
    light_sleep_seconds             DOUBLE,
    deep_sleep_seconds              DOUBLE,
    rem_sleep_seconds               DOUBLE,
    awake_seconds                   DOUBLE,
    interruptions                   INTEGER,
    short_interruption_duration_seconds DOUBLE,
    long_interruption_duration_seconds  DOUBLE,
    unknown_sleep_seconds           DOUBLE,
    average_hr_bpm                  DOUBLE,
    min_hr_bpm                      DOUBLE,
    average_ppi_ms                  DOUBLE,
    rmssd_ms                        DOUBLE,
    sdnn_ms                         DOUBLE,
    breathing_rate_bpm              DOUBLE,
    snoring_seconds                 DOUBLE,
    mean_skin_temperature_celsius   DOUBLE,
    temperature_deviation_celsius   DOUBLE,
    ingested_at                     TIMESTAMPTZ DEFAULT current_timestamp
)
"""

DDL_SLEEP_SESSIONS_IDX = """
CREATE INDEX IF NOT EXISTS idx_sleep_user_time
    ON sleep_sessions (user_id, start_time)
"""

DDL_SLEEP_STAGE_INTERVALS = """
CREATE TABLE IF NOT EXISTS sleep_stage_intervals (
    sleep_session_id  VARCHAR     NOT NULL,
    start_time        TIMESTAMPTZ NOT NULL,
    end_time          TIMESTAMPTZ NOT NULL,
    stage             VARCHAR     NOT NULL,
    duration_seconds  DOUBLE      NOT NULL
)
"""

DDL_SLEEP_STAGE_INTERVALS_IDX = """
CREATE INDEX IF NOT EXISTS idx_stage_intervals_session
    ON sleep_stage_intervals (sleep_session_id)
"""

# ---------------------------------------------------------------------------
# Daily metrics tables (composite PK: user_id + record_date)
# ---------------------------------------------------------------------------

DDL_RECOVERY_METRICS = """
CREATE TABLE IF NOT EXISTS recovery_metrics (
    user_id                          VARCHAR NOT NULL,
    record_date                      DATE    NOT NULL,
    provider                         VARCHAR NOT NULL,
    recovery_score                   DOUBLE  NOT NULL,
    rmssd_ms                         DOUBLE,
    sdnn_ms                          DOUBLE,
    resting_hr_bpm                   DOUBLE,
    mean_skin_temperature_celsius    DOUBLE,
    hrv_baseline_ms                  DOUBLE,
    resting_hr_baseline_bpm          DOUBLE,
    contrib_hrv_z_score              DOUBLE,
    contrib_resting_hr_z_score       DOUBLE,
    contrib_sleep_score              DOUBLE,
    contrib_previous_strain_score    DOUBLE,
    contrib_temperature_deviation_celsius DOUBLE,
    contrib_nightly_recharge_score   DOUBLE,
    contrib_fitness_load_z_score     DOUBLE,
    updated_at                       TIMESTAMPTZ DEFAULT current_timestamp,
    PRIMARY KEY (user_id, record_date)
)
"""

DDL_STRAIN_METRICS = """
CREATE TABLE IF NOT EXISTS strain_metrics (
    user_id        VARCHAR NOT NULL,
    record_date    DATE    NOT NULL,
    provider       VARCHAR NOT NULL,
    strain_score   DOUBLE  NOT NULL,
    cardio_load    DOUBLE  NOT NULL,
    muscle_load    DOUBLE,
    acute_load     DOUBLE,
    chronic_load   DOUBLE,
    acwr           DOUBLE,
    session_count  INTEGER DEFAULT 0,
    session_ids    JSON    DEFAULT '[]',
    updated_at     TIMESTAMPTZ DEFAULT current_timestamp,
    PRIMARY KEY (user_id, record_date)
)
"""

DDL_SLEEP_METRICS = """
CREATE TABLE IF NOT EXISTS sleep_metrics (
    user_id                  VARCHAR NOT NULL,
    record_date              DATE    NOT NULL,
    provider                 VARCHAR NOT NULL,
    sleep_session_id         VARCHAR,
    sleep_score              DOUBLE  NOT NULL,
    total_sleep_seconds      DOUBLE  NOT NULL,
    time_in_bed_seconds      DOUBLE,
    sleep_efficiency_pct     DOUBLE,
    sleep_latency_seconds    DOUBLE,
    deep_sleep_pct           DOUBLE,
    rem_sleep_pct            DOUBLE,
    light_sleep_pct          DOUBLE,
    awake_pct                DOUBLE,
    short_interruption_duration_seconds DOUBLE,
    long_interruption_duration_seconds  DOUBLE,
    unknown_sleep_pct        DOUBLE,
    rmssd_ms                 DOUBLE,
    average_hr_bpm           DOUBLE,
    sleep_consistency_score  DOUBLE,
    updated_at               TIMESTAMPTZ DEFAULT current_timestamp,
    PRIMARY KEY (user_id, record_date)
)
"""

DDL_POLAR_CARDIO_LOAD = """
CREATE TABLE IF NOT EXISTS polar_cardio_load (
    user_id     VARCHAR NOT NULL,
    date        DATE    NOT NULL,
    cardio_load DOUBLE,
    strain      DOUBLE,
    tolerance   DOUBLE,
    updated_at  TIMESTAMPTZ DEFAULT current_timestamp,
    PRIMARY KEY (user_id, date)
)
"""

# Ordered list used by the migration runner
ALL_DDL: list[str] = [
    DDL_MIGRATIONS_TABLE,
    DDL_ACTIVITY_SESSIONS,
    DDL_ACTIVITY_SESSIONS_IDX,
    DDL_SLEEP_SESSIONS,
    DDL_SLEEP_SESSIONS_IDX,
    DDL_SLEEP_STAGE_INTERVALS,
    DDL_SLEEP_STAGE_INTERVALS_IDX,
    DDL_RECOVERY_METRICS,
    DDL_STRAIN_METRICS,
    DDL_SLEEP_METRICS,
    DDL_POLAR_CARDIO_LOAD,
]
