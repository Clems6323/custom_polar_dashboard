---
name: timeseries-engineering
description: Defines standards for efficient physiological time-series processing, storage, aggregation, and analytics performance.
---

# Purpose

This skill governs handling of large physiological time-series datasets.

The platform must efficiently process:
- HR samples
- PPI intervals
- temperature streams
- sleep stages
- activity timelines
- rolling analytics

---

# Core Principles

Optimize for:
- scalability
- vectorized computation
- efficient aggregation
- incremental processing
- low memory overhead

---

# Preferred Technologies

Prefer:
- polars
- pyarrow
- DuckDB

Use pandas only where appropriate.

---

# Storage Guidance

Preferred formats:
- parquet
- DuckDB

Avoid:
- large CSV pipelines
- repeated JSON parsing
- inefficient row-based storage

---

# Time Handling Rules

Always:
- store timestamps in UTC
- preserve timezone metadata
- use ISO-8601 timestamps

Avoid:
- naive datetime objects
- implicit timezone assumptions

---

# Rolling Analytics

Preferred techniques:
- vectorized rolling windows
- incremental aggregation
- lazy execution

Avoid:
- Python loops over samples
- row-by-row processing

---

# Sampling Guidance

Support:
- irregular sampling
- missing samples
- partial nights
- device interruptions

Analytics must degrade gracefully.

---

# Resampling Rules

When resampling:
- preserve physiological meaning
- avoid excessive interpolation
- document assumptions

Avoid:
- over-smoothing
- unrealistic interpolation

---

# Performance Constraints

The system should support:
- months to years of data
- minute-level signals
- rolling trend analysis

Avoid loading unnecessary datasets into memory.

---

# Query Guidance

Prefer:
- predicate pushdown
- lazy filtering
- columnar aggregation

Avoid:
- full-table scans
- duplicated transformations

---

# Canonical Model Rules

Normalize all providers into:
- canonical timestamps
- canonical units
- canonical event schemas

Never leak provider-specific structures downstream.

---

# Testing Rules

Test:
- timezone handling
- DST transitions
- missing data
- corrupted samples
- irregular intervals
- large datasets

---

# Code Generation Rules

When generating time-series code:
- prefer vectorization
- minimize memory copies
- keep pipelines composable
- avoid hidden mutation
- keep transformations explicit