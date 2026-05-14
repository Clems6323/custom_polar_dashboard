---
name: polar-integration
description: Defines best practices for Polar AccessLink ingestion, BLE streaming, normalization, and provider abstraction.
---

# Purpose

This skill governs all Polar integrations.

Supported integrations:
- Polar AccessLink API
- Polar BLE SDK

Reference:
- https://github.com/polarofficial/accesslink-example-python
- https://github.com/polarofficial/polar-ble-sdk

---

# Core Rule

Polar-specific schemas MUST remain isolated inside ingestion modules.

Never leak:
- raw AccessLink payloads
- BLE-specific structures
- provider naming conventions

into domain analytics.

---

# AccessLink Responsibilities

The ingestion layer should support:
- OAuth2
- token persistence
- incremental synchronization
- retries/backoff
- transactional endpoints
- historical sync

---

# BLE Responsibilities

Prepare architecture for:
- async streaming
- live HR ingestion
- live PPI ingestion
- event-driven pipelines

Even if partially implemented initially, the architecture must support future live streaming.

---

# Normalization Rules

All ingestion must transform data into canonical entities.

Examples:
- ActivitySession
- SleepSession
- HeartRateSample
- PPISample
- TemperatureSample

---

# Retry Guidance

Implement:
- exponential backoff
- retry limits
- recoverable sync states

Avoid:
- infinite retries
- silent failures

---

# Sync Design

Prefer:
- incremental sync
- idempotent ingestion
- resumable transactions

Avoid:
- full-history reimports
- duplicate event creation

---

# Authentication Rules

Use:
- secure token storage
- refresh-token support
- environment configuration

Never:
- hardcode secrets
- embed credentials in code

---

# BLE Design Rules

Prefer:
- async event handling
- streaming pipelines
- event queues
- typed streaming events

Avoid:
- blocking BLE loops
- UI-coupled BLE code

---

# Provider Isolation

The rest of the platform should never know:
- which Polar endpoint produced data
- how BLE packets are structured

Analytics should operate ONLY on canonical models.

---

# Error Handling

All ingestion must:
- log failures clearly
- expose sync state
- expose retryability

Avoid silent ingestion corruption.

---

# Testing Requirements

Test:
- malformed payloads
- missing fields
- partial syncs
- token expiration
- duplicate ingestion
- timezone handling

---

# Code Generation Rules

When generating Polar integrations:
- keep adapters isolated
- normalize aggressively
- keep ingestion stateless where possible
- preserve provider abstraction