---
name: testing-strategy
description: Defines testing philosophy, analytics validation, fixture strategy, and reliability requirements for the platform.
---

# Purpose

This skill defines testing standards for the entire platform.

The system processes physiological analytics and MUST prioritize:
- correctness
- reproducibility
- deterministic outputs
- regression protection

---

# Testing Philosophy

Prefer:
- deterministic tests
- explicit fixtures
- small focused tests
- analytics validation

Avoid:
- brittle integration-heavy suites
- hidden randomness
- flaky timing-dependent tests

---

# Required Test Categories

The platform should include tests for:
- analytics correctness
- scoring systems
- ingestion normalization
- repository behavior
- schema validation
- timezone handling
- rolling windows
- recovery calculations

---

# Analytics Testing

All physiological calculations must be tested.

Examples:
- RMSSD
- SDNN
- rolling baselines
- acute/chronic ratio
- sleep scoring
- recovery scoring

---

# Fixture Rules

Prefer:
- synthetic physiological datasets
- deterministic fixtures
- explicit edge-case fixtures

Avoid:
- random uncontrolled data
- oversized fixtures

---

# Edge Cases

Always test:
- missing samples
- partial nights
- noisy HRV
- abnormal temperature
- timezone changes
- DST transitions
- duplicate ingestion
- empty datasets

---

# Schema Validation

All Pydantic models should have:
- validation tests
- serialization tests
- backward compatibility checks

---

# Integration Testing

Integration tests should validate:
- ingestion → normalization
- normalization → analytics
- analytics → services

Avoid giant end-to-end monolithic tests.

---

# Performance Testing

Include performance tests for:
- large datasets
- rolling aggregations
- multi-month analytics
- DuckDB queries

---

# Mocking Guidance

Prefer:
- repository mocks
- deterministic adapters
- fake providers

Avoid excessive mocking of internal business logic.

---

# Streamlit Testing

UI tests should focus on:
- component rendering
- navigation
- state handling

Do NOT place analytics assertions in UI tests.

---

# CI Expectations

Tests should run:
- automatically
- deterministically
- reproducibly

Prefer fast feedback loops.

---

# Code Coverage Guidance

Prioritize coverage for:
- analytics
- ingestion
- scoring
- normalization

Coverage percentage alone is NOT the goal.

Correctness matters more than arbitrary coverage metrics.

---

# Code Generation Rules

When generating tests:
- keep tests readable
- isolate responsibilities
- use explicit naming
- test edge cases first
- avoid fragile assertions