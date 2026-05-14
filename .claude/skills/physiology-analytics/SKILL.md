---
name: physiology-analytics
description: Implements scientifically grounded physiological analytics, HRV metrics, recovery scoring, sleep analysis, and strain modeling.
---

# Purpose

This skill governs all physiological analytics and scoring systems.

The goal is to produce:
- explainable
- deterministic
- testable
- evidence-aligned analytics

Avoid pseudo-scientific or opaque scoring systems.

---

# Core Analytics Domains

The system computes:
- strain
- sleep quality
- recovery/readiness
- HRV trends
- physiological deviations
- training load
- baseline shifts

---

# HRV Standards

Preferred metrics:
- RMSSD
- SDNN
- resting HR deviation
- nightly HR trends
- rolling baselines
- z-score deviations

Avoid:
- proprietary unexplained formulas
- arbitrary magic coefficients
- undocumented heuristics

---

# Baseline Methodology

All readiness/recovery metrics should normalize against:
- rolling personal baselines
- historical trends
- intra-user variability

Prefer:
- 7-day baselines
- 14-day baselines
- 28-day baselines

over fixed population assumptions.

---

# Recovery Modeling

Recovery calculations may include:
- nightly recharge
- RMSSD deviation
- resting HR deviation
- sleep quality
- skin temperature deviation
- previous strain
- accumulated fatigue

Recovery scores should:
- be explainable
- expose contributors
- expose confidence
- handle missing data gracefully

---

# Sleep Analytics

Preferred sleep features:
- sleep duration
- sleep consistency
- wake interruptions
- sleep stages
- overnight HR
- overnight PPI
- overnight temperature

Avoid simplistic “hours slept only” scoring.

---

# Strain Modeling

Preferred strain indicators:
- training load
- cardio load
- session intensity
- duration
- frequency
- acute/chronic ratio

Support:
- TRIMP-like approaches
- rolling cumulative load
- intensity distribution

---

# Explainability Requirements

All scores must:
- expose contributing factors
- document formulas
- avoid black-box outputs

Prefer transparent weighted models over opaque ML.

---

# Numerical Best Practices

Prefer:
- vectorized operations
- deterministic outputs
- stable rolling windows
- explicit units

Avoid:
- hidden implicit unit conversions
- unstable normalization
- noisy overfitting

---

# Missing Data Handling

Analytics MUST:
- tolerate incomplete nights
- expose confidence levels
- degrade gracefully
- avoid fabricated precision

Never silently impute critical physiological metrics.

---

# Statistical Guidance

Preferred techniques:
- z-score normalization
- rolling averages
- exponentially weighted smoothing
- percentile comparisons
- deviation analysis

Avoid:
- over-engineered ML pipelines
- unsupported causal claims

---

# Documentation Requirements

For every scoring system:
- explain assumptions
- explain weights
- explain normalization
- explain limitations

---

# Testing Requirements

Every physiological metric must have:
- deterministic tests
- edge-case coverage
- validation fixtures

Test:
- low HRV
- missing samples
- noisy signals
- abnormal temperature
- overtraining patterns

---

# Important Constraints

Never:
- present medical diagnoses
- imply clinical accuracy
- claim validated medical readiness

This is a wellness/performance analytics system, not a medical device.