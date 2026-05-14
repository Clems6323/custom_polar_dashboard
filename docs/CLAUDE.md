# CLAUDE.md

## Project Overview

This project is a production-grade physiological analytics platform focused on Polar wearable devices and recovery analytics.

The application provides:
- strain analysis
- sleep analysis
- recovery/readiness scoring
- physiological trend visualization
- long-term health analytics
- real-time streaming preparation

The platform is inspired by:
- Whoop
- Oura
- Garmin readiness/recovery systems
- Polar Nightly Recharge

Primary UI:
- Streamlit dashboard application

Primary language/runtime:
- Python 3.12

Package/dependency management:
- uv

Core design goals:
- modular architecture
- strong typing
- MCP compatibility
- reusable analytics engine
- extensibility for additional wearable providers
- separation between UI and domain logic

---

# Core Product Requirements

The application exposes 3 major health indicators:

## 1. Strain

Derived from:
- training load
- cardio load
- activity intensity
- session duration
- cumulative load
- recent training history
- acute/chronic load ratios

Visualizations:
- strain score
- weekly trends
- training distribution
- activity load breakdown
- load heatmaps

---

## 2. Sleep

Derived from:
- PPI variability
- overnight HR
- accelerometer movement
- sleep interruptions
- sleep duration
- sleep stages
- skin temperature evolution

Visualizations:
- sleep stages timeline
- HR/PPI overnight graphs
- temperature curves
- sleep consistency
- multi-night comparisons

---

## 3. Recovery

Derived from:
- nightly recharge
- nightly PPI
- resting HR
- skin temperature
- previous strain
- previous sleep score
- rolling physiological baselines

Visualizations:
- readiness score
- recovery trends
- physiological deviations
- contributor analysis
- strain vs recovery correlations

---

# Technical Stack

## Required Technologies

- Python 3.12
- Streamlit
- uv
- pandas
- polars
- numpy
- scipy
- plotly
- pydantic v2
- DuckDB
- pyarrow
- pytest
- ruff
- mypy

---

# Architecture Principles

The system MUST follow clean architecture principles.

## Mandatory Separation

The following layers MUST remain independent:

### 1. Domain Layer
Pure Python only.

Must NOT import:
- Streamlit
- database frameworks
- UI libraries

Contains:
- entities
- analytics
- physiological computations
- scoring engines
- business rules

---

### 2. Ingestion Layer

Responsible for:
- Polar API synchronization
- BLE streaming
- CSV/JSON imports
- normalization
- validation
- canonical model conversion

All provider-specific logic stays here.

---

### 3. Storage Layer

Responsible for:
- persistence
- query abstraction
- parquet support
- DuckDB/SQLite interactions
- caching

---

### 4. Service Layer

Responsible for:
- orchestration
- analytics pipelines
- MCP-compatible APIs
- structured outputs

---

### 5. UI Layer

Responsible ONLY for:
- visualization
- user interactions
- dashboard rendering
- navigation

Must never contain business logic.

---

# MCP Compatibility

The core analytics engine MUST be reusable outside Streamlit.

Design services to support:
- AI agent integrations
- MCP tools
- structured JSON outputs
- reusable analytics APIs

The MCP layer should expose tools such as:
- get_sleep_score
- get_recovery_score
- get_strain_score
- get_training_load
- get_sleep_trends
- get_temperature_deviation

All MCP outputs must:
- use typed schemas
- be deterministic
- be UI-independent

---

# Polar Integrations

## Official SDKs

Use:
- https://github.com/polarofficial/accesslink-example-python
- https://github.com/polarofficial/polar-ble-sdk

Reference:
- https://www.polar.com/en/developers

---

## Polar AccessLink API

Used for:
- historical synchronization
- exercises
- sleep
- nightly recharge
- activity summaries
- physiological metrics

Requirements:
- OAuth2 flow
- token persistence
- incremental synchronization
- retry/backoff handling
- transactional endpoint handling

Do NOT copy the example project architecture directly.
Refactor into production-grade services.

---

## Polar BLE SDK

Used for:
- real-time HR streaming
- PPI streaming
- future live monitoring
- event-driven analytics

Prepare architecture for:
- async ingestion
- websocket pipelines
- streaming analytics
- event bus patterns

Even if BLE support is partial initially, architecture MUST support future live ingestion.

---

# Canonical Data Model

All provider-specific schemas MUST be transformed into internal canonical models.

Never leak Polar-specific structures into domain logic.

Canonical entities should include:
- ActivitySession
- SleepSession
- SleepStageInterval
- HeartRateSample
- PPISample
- TemperatureSample
- RecoveryMetrics
- StrainMetrics
- SleepMetrics
- DailyActivityTotals
- CardioLoad

Use:
- Pydantic v2
- strong typing
- validation
- explicit units

---

# Physiological Analytics

Implement reusable analytics utilities for:
- RMSSD
- SDNN
- HRV trend analysis
- rolling baselines
- z-score deviation analysis
- acute/chronic load ratio
- sleep consistency
- circadian analysis
- recovery scoring

Analytics should be:
- explainable
- deterministic
- testable

Avoid black-box ML unless explicitly requested.

---

# Streamlit UX Requirements

The UI should feel:
- premium
- minimal
- modern
- data-dense
- performance-oriented

Use:
- sidebar navigation
- reusable metric cards
- trend indicators
- sparklines
- gauges
- Plotly charts
- responsive layouts

Support:
- dark mode
- caching
- session state

---

# Folder Structure

Expected structure:

```text
src/
  domain/
  ingestion/
  services/
  storage/
  mcp/
  ui/
  utils/

tests/
docs/
scripts/
configs/
data/
```

Actual implemented structure:

```text
src/
  domain/
    models/          # All canonical entities (Pydantic v2, frozen)

  ingestion/
    polar_accesslink/
      endpoints/
    normalization/

  services/
    analytics/       # HRV (RMSSD, SDNN), rolling baselines, z-scores
    scoring/         # SleepScorer, StrainScorer, RecoveryScorer
    readiness/       # ReadinessPipeline orchestration

  storage/
    repositories/
    duckdb/          # schema, migrations, connection
    parquet/         # writer, reader, partitions

  polar_mcp/         # package name avoids conflict with polar-ble-sdk
    tools/
    schemas/
    server.py        # entry point: python -m polar_mcp.server

  ui/
    streamlit/
      pages/
      components/
      charts/
      sync.py        # in-app sync helpers

  utils/
```

---

# Coding Standards

## Mandatory

- full typing
- mypy clean
- ruff clean
- modular functions
- small files
- comprehensive docstrings
- explicit naming
- unit-tested analytics

---

## Avoid

- monolithic files
- hidden state
- global mutable state
- tight coupling
- UI business logic
- provider-specific logic in analytics

---

# Performance Expectations

Optimize for:
- large time-series datasets
- incremental sync
- efficient aggregation
- vectorized computations

Prefer:
- polars
- pyarrow
- DuckDB

over inefficient pandas-only workflows when appropriate.

---

# Development Workflow

Development must happen incrementally.

## Phase Order

1. Architecture — **COMPLETE** (clean layered structure, pyproject.toml, settings, logging)
2. Domain models — **COMPLETE** (ActivitySession, SleepSession, SleepMetrics, RecoveryMetrics, StrainMetrics, enums; 58 tests passing)
3. Storage layer — **COMPLETE** (DuckDB repositories, migrations, protocol interfaces; 58 tests passing)
4. Polar ingestion — **COMPLETE** (OAuth2 auth, AccessLink v3 client, all endpoints, normalization, sync orchestrator; 47 ingestion tests; live sync verified: 29 sleep nights, 27 recharge nights)
5. Analytics engine — **COMPLETE** (HRV analytics, sleep/strain/recovery scoring, readiness pipeline; 92 tests; ruff clean)
6. MCP layer — **COMPLETE** (FastMCP server, 6 typed tools, Pydantic v2 schemas, confidence metadata; 44 tests; local package renamed to polar_mcp to avoid SDK naming conflict)
7. Streamlit UI — **COMPLETE** (4 pages: Overview, Sleep, Strain, Recovery; sidebar navigation; dark theme; reusable metric cards and section headers; DuckDB read_only per-query connections via context manager; `@st.cache_data` for query-result caching; no persistent cached connection; ruff clean)
8. Visualizations — **COMPLETE** (sleep schedule bedtime/wake chart; recovery contributor radar spider chart; sleep→recovery correlation scatter with Pearson r and trend line; week-over-week comparison on Overview; all charts backed by real live Polar data; 26 paired sleep→recovery data points verified)
9. Testing — **COMPLETE** (348 tests passing; 99% line coverage on all testable source; `fail_under = 90` enforced in pyproject.toml; omit rules exclude legitimately untestable files: Streamlit UI, Polar API client/endpoints, MCP server bootstrap, DuckDB connection factory; covers domain models, storage repos, Parquet I/O, migrations, normalization, analytics, scoring, readiness pipeline, MCP tools)
10. Deployment — **COMPLETE** (two-stage Dockerfile with `uv sync --frozen --no-dev`; docker-compose.yml with `./data` volume mount and healthcheck; .dockerignore; scripts/init_db.py and scripts/run_sync.py for headless operation; Makefile extended with `dashboard`, `mcp`, `init-db`, `sync`, `auth`, `demo`, `test-cov`, `check`, `docker-build`, `docker-up`, `docker-down`, `docker-logs`, `docker-shell` targets; uv.lock tracked in git for `--frozen` reproducibility)

After each phase:
- explain design decisions
- explain tradeoffs
- wait for confirmation before proceeding

Do NOT generate the entire project in one step.

---

# Testing Requirements

Use:
- pytest
- pytest-cov (`fail_under = 90` enforced)

Required tests:
- scoring correctness
- analytics edge cases
- ingestion normalization
- schema validation
- trend calculations
- recovery calculations
- migration idempotency
- pipeline error isolation
- Parquet round-trips and edge cases
- MCP tool output schema validation

Prefer deterministic fixtures.

Omit from coverage (legitimately untestable without live credentials or a running process):
- `src/ui/streamlit/` — Streamlit runtime
- `src/ingestion/polar_accesslink/auth.py`, `client.py`, `endpoints/`, `sync.py` — live API
- `src/polar_mcp/server.py` — FastMCP server bootstrap
- `src/storage/duckdb/connection.py` — connection factory
- `src/utils/logging.py` — logging bootstrap

---

# Deployment Requirements

Support:
- local development
- Docker deployment
- future cloud deployment

Include:
- Dockerfile (two-stage: `builder` installs deps with uv, `runtime` is lean)
- docker-compose.yml (mounts `./data`, passes `.env`, healthcheck on `/_stcore/health`)
- .dockerignore (excludes `.venv/`, `tests/`, `data/`, `.env`, IDE files)
- Makefile with `docker-*` targets
- environment configuration via `.env` / `.env.example`
- scripts/init_db.py — headless DB initialisation
- scripts/run_sync.py — headless full data sync

Key decisions:
- `uv.lock` is committed (not gitignored) — required for `uv sync --frozen` in Docker
- `PYTHONPATH=/app/src:/app` replaces editable install in container
- OAuth2 token acquired on host, persisted in `data/tokens/`, shared into container via volume

---

# Documentation Expectations

Generate:
- architecture docs
- API docs
- setup instructions
- ingestion guides
- scoring methodology docs

Document:
- assumptions
- formulas
- physiological interpretations

---

# Important Constraints

## Do NOT

- tightly couple Streamlit to analytics
- hardcode Polar-specific assumptions
- build toy/demo-only architecture
- generate giant monolithic scripts

---

# Priorities

Priority order:

1. Clean architecture
2. Data correctness
3. Extensibility
4. Explainable analytics
5. MCP compatibility
6. UX polish
7. Performance optimization

---

# Expected Behavior From Claude

When generating code:
- proceed incrementally
- explain reasoning
- justify architecture decisions
- prefer maintainability over shortcuts
- ask before major refactors
- avoid speculative complexity
- keep interfaces explicit and typed

When uncertain:
- prefer composable abstractions
- prefer testability
- prefer provider-agnostic models

Always generate production-quality code.