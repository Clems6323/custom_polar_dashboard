---
name: mcp-tool-design
description: Defines MCP-compatible tool architecture, typed schemas, deterministic services, and reusable analytics APIs.
---

# Purpose

This skill ensures the platform remains fully MCP-compatible and reusable by AI agents.

The MCP layer must expose:
- deterministic services
- typed schemas
- structured outputs
- provider-agnostic analytics

---

# MCP Design Principles

Tools must be:
- stateless
- deterministic
- typed
- composable
- reusable

Avoid:
- hidden session state
- UI dependencies
- provider-specific outputs

---

# Tool Design Rules

Each MCP tool should:
- perform one responsibility
- expose typed inputs
- expose typed outputs
- validate schemas explicitly

---

# Example Tools

Examples include:
- get_sleep_score
- get_recovery_score
- get_strain_score
- get_training_load
- get_sleep_trends
- get_temperature_deviation
- get_hrv_baseline

---

# Output Rules

Tool outputs should:
- use structured JSON
- expose metadata
- expose confidence
- expose contributors
- expose timestamps

Avoid free-form text outputs.

---

# Schema Standards

Use:
- Pydantic v2
- explicit units
- ISO timestamps
- versioned schemas

Never use ambiguous field names.

Prefer:
- resting_hr_bpm
- rmssd_ms
- sleep_duration_minutes

over:
- hr
- hrv
- duration

---

# Service Separation

The MCP layer should call:
- services
- repositories
- analytics engines

Never:
- call Streamlit directly
- access provider SDKs directly
- embed UI formatting

---

# Error Handling

All tools should:
- validate inputs
- return structured errors
- expose recoverable states

Avoid:
- silent failures
- generic exceptions

---

# Determinism Requirements

Analytics tools must:
- produce reproducible outputs
- avoid hidden randomness
- avoid time-dependent side effects

---

# Extensibility Requirements

The MCP layer should support:
- future wearable providers
- future AI agents
- future external APIs

Avoid provider-specific contracts.

---

# Performance Rules

Prefer:
- cached queries
- efficient aggregation
- lazy computation

Avoid:
- loading full datasets unnecessarily
- recomputing rolling windows repeatedly

---

# Documentation Rules

Each tool must document:
- purpose
- schema
- units
- assumptions
- limitations

---

# Code Generation Rules

When generating MCP tools:
- keep schemas explicit
- keep services small
- preserve statelessness
- separate orchestration from computation
- avoid giant multi-purpose endpoints