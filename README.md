# Polar Dashboard

A production-grade physiological analytics platform for Polar wearable devices.
Tracks **strain**, **sleep**, and **recovery** with the depth of Whoop or Oura, built on your own data.

> **Status:** All 10 phases complete — architecture, domain models, storage, ingestion, analytics engine, MCP layer, Streamlit UI, visualizations, full test suite (375 tests, 99% coverage), and Docker deployment.

---

## How it works

```
Polar device
    │
    ▼
Polar AccessLink API  ──OAuth2──►  scripts/polar_auth.py   (one-time)
    │
    ▼
scripts/run_sync.py
    │
    ├── Exercise transactions   ──normalize──► ActivitySession  ──► DuckDB
    ├── Sleep data              ──normalize──► SleepSession         DuckDB
    │                                         SleepMetrics      ──► DuckDB
    ├── Nightly Recharge        ──normalize──► RecoveryMetrics  ──► DuckDB
    └── Activity summaries      ──normalize──► DailyActivityTotals ─► DuckDB

DuckDB + Parquet
    │
    ├── Analytics engine        (HRV, ACWR, baselines, sleep/strain/recovery scoring)
    ├── MCP tools               (FastMCP server, 7 typed AI-agent tools: 6 query + 1 action)
    └── Streamlit dashboard     (Overview / Sleep / Strain / Recovery — dark theme)
```

### Data sources

| Source | What it provides | Sync method |
|---|---|---|
| Exercise transactions | Workouts, HR zones, training load, distance | POST→GET→PUT transaction |
| Sleep data | Stage durations, hypnogram, continuity score | List available dates, GET each |
| Nightly Recharge | ANS recovery rate, HRV overnight, skin temp | List available dates, GET each |
| Activity summaries | Daily steps, active calories, active duration | POST→GET→PUT transaction |

### Storage

- **DuckDB** (`data/polar_dashboard.duckdb`) — structured sessions and daily metrics. Seven tables: `activity_sessions`, `sleep_sessions`, `sleep_stage_intervals`, `recovery_metrics`, `strain_metrics`, `sleep_metrics`, `polar_cardio_load`.
- **Parquet** (`data/parquet/`) — high-frequency time-series (heart rate, PPI, skin temperature), partitioned by `{sample_type}/{user_id}/{YYYY-MM-DD}/data.parquet`.

### Architecture layers

```
domain/       Pure Python entities and business rules. No external imports.
ingestion/    Polar API client, OAuth2 flow, normalization to canonical models.
storage/      DuckDB repositories and Parquet reader/writer.
services/     Analytics pipelines, scoring engines, readiness pipeline.
mcp/          AI-agent tools with typed JSON schemas (FastMCP server).
ui/           Streamlit dashboard — visualization only, no business logic.
configs/      Pydantic-settings config loaded from environment / .env.
```

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Runtime |
| [uv](https://docs.astral.sh/uv/) | latest | Package management |
| Polar Flow account | — | Data source |
| Polar AccessLink app | — | API credentials |

### Register a Polar AccessLink application

1. Go to [admin.polaraccesslink.com](https://admin.polaraccesslink.com)
2. Create a new application
3. Set the redirect URI to `http://localhost:8000/auth/polar/callback`
4. Copy the **Client ID** and **Client Secret**

---

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd polar-dashboard

# Install all dependencies
uv sync
```

---

## Configuration

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Open `.env` and set the required values:

```env
# --- Polar AccessLink credentials (required for sync) ---
POLAR_CLIENT_ID=your-client-id-here
POLAR_CLIENT_SECRET=your-client-secret-here
POLAR_REDIRECT_URI=http://localhost:8000/auth/polar/callback

# --- Storage paths (defaults work out of the box) ---
STORAGE_DATA_DIR=data
STORAGE_DUCKDB_PATH=data/polar_dashboard.duckdb
STORAGE_PARQUET_DIR=data/parquet
STORAGE_TOKEN_PATH=data/tokens/polar_token.json

# --- Application behaviour ---
APP_DEBUG=false
APP_LOG_LEVEL=INFO
APP_DEMO_MODE=false
```

### Environment variable reference

| Variable | Default | Description |
|---|---|---|
| `POLAR_CLIENT_ID` | — | OAuth2 client ID from Polar developer console |
| `POLAR_CLIENT_SECRET` | — | OAuth2 client secret |
| `POLAR_REDIRECT_URI` | `http://localhost:8000/auth/polar/callback` | Must match your registered app |
| `STORAGE_DATA_DIR` | `data` | Root directory for all local data files |
| `STORAGE_DUCKDB_PATH` | `data/polar_dashboard.duckdb` | DuckDB database file |
| `STORAGE_PARQUET_DIR` | `data/parquet` | Root for Parquet time-series files |
| `STORAGE_TOKEN_PATH` | `data/tokens/polar_token.json` | Persisted OAuth2 token |
| `APP_DEBUG` | `false` | Verbose debug logging |
| `APP_LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `APP_DEMO_MODE` | `false` | Use synthetic data (no Polar sync required) |

---

## Quick start

### 1 — Initialise the database

```bash
make init-db
# or:
uv run python scripts/init_db.py
```

Runs all DuckDB migrations and creates the schema. Safe to re-run — migrations are idempotent.

### 2 — Authorize with Polar (one-time)

```bash
make auth
# or:
uv run python scripts/polar_auth.py
```

Opens a browser to the Polar authorization page, starts a local HTTP server on port 8000,
captures the OAuth2 callback, and saves the token to `data/tokens/polar_token.json`.
You only need to do this once; the token is refreshed automatically on subsequent syncs.

### 3 — Sync your data

```bash
make sync
# or:
uv run python scripts/run_sync.py
```

Runs four independent pipelines: exercises, sleep, nightly recharge, activity summaries.
Safe to run multiple times — all writes are upserts.

### 4 — Launch the dashboard

```bash
make dashboard
# or:
uv run streamlit run src/ui/streamlit/app.py
```

Opens the dashboard at `http://localhost:8501`.
Pages: **Overview**, **Sleep**, **Strain**, **Recovery**, **Metrics Guide**.
The dashboard connects read-only to DuckDB and can run while a sync is in progress.
You can also trigger a sync directly from the sidebar without leaving the browser.

---

## Running the ingestion pipeline

### Step 1 — Authorize with Polar (one-time)

```bash
uv run python scripts/polar_auth.py
# or:
make auth
```

This will:
1. Open your browser to the Polar authorization page
2. Start a local HTTP server on port 8000 to capture the OAuth2 callback
3. Exchange the authorization code for an access token
4. Save the token to `data/tokens/polar_token.json`

You only need to do this once. The token is refreshed automatically on subsequent syncs.

### Step 2 — Sync your data

```bash
uv run python scripts/run_sync.py
# or:
make sync
```

The sync runs four pipelines in order:

1. **Exercises** — fetches new workouts via transaction lifecycle, normalizes to `ActivitySession`, stores in DuckDB
2. **Sleep** — fetches all available nights, normalizes to `SleepSession` + `SleepMetrics`, stores in DuckDB
3. **Nightly Recharge** — fetches ANS recovery data, normalizes to `RecoveryMetrics`, stores in DuckDB
4. **Activity summaries** — fetches daily step/calorie totals via transaction lifecycle

Each pipeline is independent: a failure in one does not stop the others. Errors are logged and reported at the end. The sync exits with code 1 if any error occurred, so it integrates cleanly with cron or CI.

**Transaction safety:** exercise and activity transactions are only committed after all records in the batch are successfully fetched and normalized. An error mid-batch leaves the transaction open so the next sync retries it.

### Re-syncing

The sync is idempotent. Running it multiple times is safe — all repository writes use `ON CONFLICT DO UPDATE` (upsert semantics). Sleep and nightly recharge endpoints always return the full history, so previously synced records are refreshed.

---

## MCP server

Start the FastMCP server exposing 7 typed AI-agent tools:

```bash
make mcp
# or:
uv run python -m polar_mcp.server
```

### Query tools (read-only, require synced data)

| Tool | Description |
|---|---|
| `get_sleep_score` | Sleep quality score + architecture breakdown (duration, efficiency, deep/REM/light %) for a single night |
| `get_sleep_trends` | Per-night scores with summary averages over a date range |
| `get_strain_score` | Daily training strain score and ACWR for a specific date |
| `get_training_load` | Training load time-series with peak and average summaries over a date range |
| `get_recovery_score` | Composite readiness score with full contributor breakdown (HRV, resting HR, sleep, strain, temperature) |
| `get_hrv_baseline` | Rolling HRV baseline statistics (RMSSD mean, std, current vs. baseline %) |

### Action tool (writes to DB, requires Polar credentials)

| Tool | Parameters | Description |
|---|---|---|
| `sync_and_analyze` | `analytics_days` (default 90) | Fetch the latest data from Polar AccessLink then immediately score the readiness analytics pipeline. Returns sync counts and scored-day counts in one response. Use this as the standard refresh action before querying any metric tools. |

### Usage from n8n (HTTP Request node)

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "sync_and_analyze",
    "arguments": { "analytics_days": 90 }
  },
  "id": 1
}
```

All tool outputs use typed Pydantic v2 schemas with explicit units, ISO timestamps, and confidence metadata.

---

## Docker deployment

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with Compose plugin

### Build and run

```bash
# Build the image and start the dashboard
make docker-up
# or:
docker compose up -d
```

The dashboard will be available at `http://localhost:8501`.

Persistent data (database, tokens, Parquet files) is mounted from `./data` into `/app/data` inside
the container, so your synced history survives container restarts.

### Other Docker commands

```bash
make docker-build   # Build the image without starting
make docker-logs    # Tail container logs
make docker-shell   # Open a shell inside the running container
make docker-down    # Stop and remove the container
```

### First-run inside Docker

The OAuth2 flow requires a browser, so complete the token acquisition on the host first:

```bash
make auth           # Run on host — saves token to data/tokens/polar_token.json
make docker-up      # Container picks up the token from the mounted data/ volume
```

### Environment variables for Docker

Set your credentials in `.env` at the project root before running `docker compose up`.
The `docker-compose.yml` passes `.env` to the container via `env_file`.

---

## Development

### Available Make targets

```
Development
  install       Install all dependencies (including dev)
  dashboard     Start the Streamlit dashboard  (localhost:8501)
  mcp           Start the MCP server
  init-db       Initialise / migrate the DuckDB database
  sync          Run a headless Polar data sync
  auth          Run the OAuth2 callback server for token acquisition
  demo          Seed synthetic data (no Polar account needed)

Quality
  test          Run the test suite (quiet)
  test-cov      Run tests with coverage report (fail under 90 %)
  lint          Lint and check imports with ruff
  format        Auto-format with ruff
  type-check    Static type-check with mypy
  check         lint + type-check + test-cov

Docker
  docker-build  Build the production Docker image
  docker-up     Start the dashboard via docker compose
  docker-down   Stop the dashboard container
  docker-logs   Tail container logs
  docker-shell  Open a shell inside the running container

Housekeeping
  clean         Remove caches, coverage artefacts, and .pyc files
```

### Running tests

```bash
make test
# with coverage:
make test-cov
# specific module:
uv run pytest tests/domain/
uv run pytest tests/storage/
uv run pytest tests/ingestion/
uv run pytest tests/services/
uv run pytest tests/mcp/
```

Current status: **375 tests passing** across domain models, storage repositories, Parquet I/O, normalization, analytics engine, MCP tools, and readiness pipeline. **99% line coverage** on all testable source files.

### Linting and type checking

```bash
uv run ruff check src tests configs   # lint
uv run ruff format src tests configs  # format
uv run mypy src                       # type check
# or all at once:
make check
```

---

## Project structure

```
polar-dashboard/
├── .env.example                      # Environment variable template
├── .dockerignore                     # Docker build exclusions
├── Dockerfile                        # Two-stage build (builder + runtime)
├── docker-compose.yml                # Compose file for local Docker deployment
├── Makefile                          # Developer shortcuts
├── pyproject.toml                    # Project metadata, deps, tool config
│
├── configs/
│   └── settings.py                   # Pydantic-settings config (PolarSettings, StorageSettings, AppSettings)
│
├── scripts/
│   ├── polar_auth.py                 # One-time OAuth2 authorization flow
│   ├── run_sync.py                   # Headless full data sync
│   ├── init_db.py                    # Database initialisation / migrations
│   └── seed_demo_data.py             # Synthetic data seeder (demo mode)
│
├── src/
│   ├── domain/
│   │   └── models/                   # Canonical entities (frozen Pydantic v2)
│   │       ├── activity.py           # ActivitySession
│   │       ├── sleep.py              # SleepSession, SleepStageInterval
│   │       ├── sleep_metrics.py      # SleepMetrics (daily aggregate)
│   │       ├── recovery.py           # RecoveryMetrics, RecoveryContributors
│   │       ├── strain.py             # StrainMetrics
│   │       ├── heart_rate.py         # HeartRateSample
│   │       ├── ppi.py                # PPISample (hr_bpm auto-derived)
│   │       ├── temperature.py        # TemperatureSample
│   │       └── enums.py              # Provider, SportType, SleepStage
│   │
│   ├── ingestion/
│   │   ├── polar_accesslink/
│   │   │   ├── auth.py               # TokenStore, PolarOAuth2
│   │   │   ├── client.py             # PolarClient (httpx + tenacity retry)
│   │   │   ├── models.py             # Raw Polar API response models
│   │   │   ├── sync.py               # SyncOrchestrator
│   │   │   └── endpoints/
│   │   │       ├── sleep.py          # SleepEndpoint, NightlyRechargeEndpoint
│   │   │       ├── exercises.py      # ExerciseEndpoint (transaction lifecycle)
│   │   │       └── activities.py     # ActivityEndpoint (transaction lifecycle)
│   │   └── normalization/
│   │       ├── utils.py              # ISO duration parser, sport mapping, UTC helpers
│   │       ├── sleep.py              # PolarSleepData → SleepSession + SleepMetrics
│   │       ├── exercise.py           # PolarExercise → ActivitySession
│   │       ├── nightly_recharge.py   # PolarNightlyRecharge → RecoveryMetrics
│   │       └── activity.py           # PolarActivitySummary → DailyActivityTotals
│   │
│   ├── storage/
│   │   ├── duckdb/
│   │   │   ├── schema.py             # DDL for all seven tables
│   │   │   ├── migrations.py         # Idempotent migration runner
│   │   │   └── connection.py         # DuckDBConnectionManager
│   │   ├── parquet/
│   │   │   ├── writer.py             # write_hr_samples, write_ppi_samples, ...
│   │   │   ├── reader.py             # read_hr_samples, read_ppi_samples, ...
│   │   │   └── partitions.py         # Path helpers for {type}/{user}/{date}/ layout
│   │   └── repositories/
│   │       ├── protocols.py          # Repository Protocol interfaces
│   │       ├── activity.py           # DuckDBActivityRepository
│   │       ├── sleep.py              # DuckDBSleepRepository
│   │       └── metrics.py            # DuckDBRecovery/Strain/SleepMetricsRepository
│   │
│   ├── services/
│   │   ├── analytics/                # HRV (RMSSD, SDNN), rolling baselines, z-scores
│   │   ├── scoring/                  # SleepScorer, StrainScorer, RecoveryScorer
│   │   └── readiness/                # ReadinessPipeline — daily readiness orchestration
│   │
│   ├── polar_mcp/                    # FastMCP server, 7 typed AI-agent tools (6 query + 1 action)
│   │   ├── server.py                 # Entry point: python -m polar_mcp.server
│   │   ├── tools/                    # get_sleep_score, get_recovery_score, ..., sync_and_analyze
│   │   └── schemas/                  # Pydantic v2 output schemas
│   │
│   └── ui/
│       └── streamlit/
│           ├── app.py                # Entry point and sidebar navigation
│           ├── sync.py               # In-app sync helpers (run_full_sync)
│           ├── pages/                # Overview, Sleep, Strain, Recovery, Metrics Guide
│           ├── components/           # Metric cards, section headers
│           └── charts/               # Plotly chart builders
│
├── tests/
│   ├── domain/test_models.py         # Entity validation, computed fields, constraints
│   ├── storage/test_repositories.py  # DuckDB upsert, query, cascade, batch ops
│   ├── storage/test_parquet.py       # Parquet round-trips, dedup, edge cases
│   ├── storage/test_migrations.py    # Migration idempotency, rename branch
│   ├── ingestion/test_normalization.py  # ISO parser, sport mapping, all normalizers
│   ├── services/                     # Scoring engines, analytics, readiness pipeline
│   └── mcp/                          # MCP tool outputs, schema validation
│
└── data/                             # Created automatically on first run
    ├── polar_dashboard.duckdb
    ├── tokens/polar_token.json
    └── parquet/
        ├── heart_rate/{user_id}/{YYYY-MM-DD}/data.parquet
        ├── ppi/{user_id}/{YYYY-MM-DD}/data.parquet
        └── temperature/{user_id}/{YYYY-MM-DD}/data.parquet
```

---

## Data model

### Domain entities

| Entity | Storage | Description |
|---|---|---|
| `ActivitySession` | DuckDB `activity_sessions` | Single workout with HR zones, training load, distance |
| `SleepSession` | DuckDB `sleep_sessions` | Full night recording with stage intervals |
| `SleepStageInterval` | DuckDB `sleep_stage_intervals` | 5-minute sleep stage windows (light/deep/REM) |
| `SleepMetrics` | DuckDB `sleep_metrics` | Daily sleep quality aggregate (score, efficiency, architecture %) |
| `RecoveryMetrics` | DuckDB `recovery_metrics` | Daily readiness score + contributor breakdown |
| `StrainMetrics` | DuckDB `strain_metrics` | Daily training load aggregate + ACWR |
| `CardioLoad` | DuckDB `polar_cardio_load` | Daily cardio and muscle load + rolling tolerance |
| `HeartRateSample` | Parquet | Per-sample HR readings |
| `PPISample` | Parquet | Peak-to-peak interval readings (HR auto-derived) |
| `TemperatureSample` | Parquet | Skin temperature readings |

### Normalization decisions

- **Sleep timestamps** are returned by Polar in local time without a timezone offset. They are stored as UTC (documented assumption; local-time display is applied in the UI layer).
- **Hypnogram** characters map as: `0`=WAKE, `1`=REM, `2`=LIGHTER NREM, `3`=LIGHT NREM, `4`=DEEP, `5`=UNKNOWN. Consecutive identical stages are merged into one `SleepStageInterval` to reduce storage.
- **Recovery score** comes from Polar's `ans_rate` field (0–100 ANS charge). Falls back to 50.0 if unavailable.
- **Resting HR** is derived from `beat_to_beat_avg` (ms) via `60 000 / ms`.
- **Sport type** mapping: `detailed_sport_info` is preferred over `sport` for more specific classification. Unknown labels map to `SportType.OTHER`.
- **Continuity score**: Polar provides a 1.0–5.0 scale, which is multiplied by 20 to produce a 20–100 value.

---

## Development phases

| Phase | Description | Status |
|---|---|---|
| 1 | Architecture scaffold | **Complete** |
| 2 | Domain models | **Complete** |
| 3 | Storage layer (DuckDB + Parquet) | **Complete** |
| 4 | Polar AccessLink ingestion | **Complete** |
| 5 | Analytics engine (RMSSD, ACWR, baselines, scoring) | **Complete** |
| 6 | MCP layer (FastMCP server, 7 typed AI-agent tools: 6 query + 1 action) | **Complete** |
| 7 | Streamlit UI (Overview / Sleep / Strain / Recovery pages, dark theme, metric cards) | **Complete** |
| 8 | Visualizations (sleep schedule, radar chart, correlation scatter, week-over-week) | **Complete** |
| 9 | Full test suite (348 tests, 99% coverage, `fail_under = 90`) | **Complete** |
| 10 | Deployment (Dockerfile, docker-compose, Makefile, init-db, run-sync scripts) | **Complete** |
