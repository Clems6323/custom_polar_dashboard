---
name: architecture-review
description: Enforces clean architecture boundaries, modularity, provider-agnostic design, and maintainable service decomposition.
---

# Purpose

This skill ensures the codebase preserves clean architecture principles and avoids long-term structural degradation.

The project is a production-grade physiological analytics platform and MUST remain:
- modular
- testable
- provider-agnostic
- MCP-compatible
- UI-independent

---

# Core Architectural Principles

## Mandatory Layer Separation

The following layers MUST remain isolated:

### Domain Layer
Contains:
- entities
- business rules
- analytics
- scoring logic
- physiological computations

Must NOT import:
- Streamlit
- database frameworks
- provider SDKs
- HTTP frameworks
- visualization libraries

---

### Ingestion Layer
Responsible ONLY for:
- external APIs
- BLE communication
- parsing
- normalization
- synchronization
- retry handling

Must transform provider-specific data into canonical domain entities.

Never expose provider-specific schemas outside ingestion.

---

### Storage Layer
Responsible ONLY for:
- persistence
- repositories
- query abstraction
- parquet/DuckDB/SQLite interactions

Must not contain analytics logic.

---

### Service Layer
Responsible for:
- orchestration
- pipelines
- aggregation coordination
- MCP-compatible interfaces

Must remain UI-independent.

---

### UI Layer
Responsible ONLY for:
- rendering
- interaction
- navigation
- visualization

Must NEVER:
- compute scores
- implement analytics
- access provider SDKs directly

---

# Dependency Rules

Allowed dependency direction:

UI → Services → Domain
Ingestion → Domain
Storage → Domain

Forbidden:
- Domain → UI
- Domain → Storage
- Domain → Provider SDKs
- Services → Streamlit
- Analytics inside UI components

---

# Architectural Priorities

Priority order:
1. Correct boundaries
2. Explicit interfaces
3. Maintainability
4. Testability
5. Extensibility
6. Performance

---

# Required Design Patterns

Prefer:
- composition over inheritance
- stateless services
- explicit interfaces
- typed contracts
- dependency injection
- immutable domain models
- repository abstractions

---

# Avoid

Do NOT generate:
- god classes
- giant utility modules
- hidden mutable state
- circular dependencies
- giant service layers
- monolithic Streamlit files
- provider-specific analytics
- tightly coupled pipelines

---

# File Size Guidance

Prefer:
- small focused modules
- explicit naming
- one responsibility per file

Strongly reconsider files larger than:
- 400 lines for services
- 300 lines for UI pages
- 500 lines for analytics modules

---

# MCP Compatibility Rules

All business logic must remain reusable independently from:
- Streamlit
- CLI
- REST APIs
- MCP tools

Analytics must be callable headlessly.

---

# Extensibility Requirements

The architecture MUST support future providers:
- Garmin
- Oura
- Apple Health
- Fitbit

Never hardcode Polar assumptions into domain logic.

---

# Code Generation Rules

When generating code:
- proceed incrementally
- explain tradeoffs
- preserve architectural boundaries
- prefer explicitness over magic
- avoid premature abstraction

Always prefer maintainable systems over rapid prototypes.