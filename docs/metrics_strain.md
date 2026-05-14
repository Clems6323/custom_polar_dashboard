# Strain Metrics

This page describes every training-load and strain metric computed by the Polar Dashboard: how the raw data is sourced, how load is estimated, and how the 0–100 strain score is derived.

---

## Input Data

Training load data comes from two separate Polar AccessLink v3 endpoints.

### Exercise Sessions (`GET /v3/exercises`)

One record per workout, retrieved after each sync.

| Field | Unit | Description |
|---|---|---|
| `cardio_load` | Arbitrary Load Units (AU) | Polar Training Load Pro cardio component — cardiovascular stress computed using Banister's TRIMP method (see below) |
| `muscle_load` | AU | Polar Training Load Pro muscle component — mechanical / neuromuscular stress |
| `duration_seconds` | seconds | Total exercise duration |
| `average_hr_bpm` | bpm | Mean heart rate during the session |
| `max_hr_bpm` | bpm | Peak heart rate during the session |
| `sport` | string | Sport type (e.g. `RUNNING`, `CYCLING`, `STRENGTH_TRAINING`) |

> **Note on Arbitrary Load Units (AU):** Polar Training Load Pro's cardio component is based on Banister's TRIMP (Training Impulse) method, which weights heart rate data according to its relationship with blood lactate accumulation (see *Session Load Estimation* below). The AU scale is calibrated so that a typical moderate endurance session produces values in the 50–150 range, and a hard interval session reaches 200–300+. Full methodology is documented in Polar's Training Load Pro white paper.

### Daily Cardio-Load Status (`GET /v3/users/cardio-load`)

One record per day, representing rolling aggregates.

| Field | Unit | Description |
|---|---|---|
| `cardio_load` | PLU | Daily cardio load (same as the sum of session `cardio_load` values) |
| `strain` | PLU | 7-day rolling mean of daily cardio load (Polar's **acute load**) |
| `tolerance` | PLU | 28-day rolling mean of daily cardio load (Polar's **chronic load** / fitness baseline) |

---

## Session Load Estimation

For each exercise session a single load value is derived using the following priority order:

```
1. session.cardio_load          (Polar TRIMP-based value — preferred)
2. minutes × (avg_hr / max_hr) × 2   (simplified TRIMP fallback)
3. minutes                       (duration-only floor, 1 AU/minute)
```

### Primary path — Polar TRIMP (Banister's method)

When `cardio_load` is available from Polar, it is used directly. Polar computes this value using Banister's **Training Impulse (TRIMP)** method, which accounts for exercise duration, mean heart rate, resting HR, maximal HR, and an exponential weighting factor that reflects the non-linear relationship between HR and blood lactate accumulation:

```
TRIMP = duration × ΔHR_ratio × e^(b × ΔHR_ratio)

where:
  ΔHR_ratio = (HR_mean – HR_rest) / (HR_max – HR_rest)
  b          = exponential weighting factor (gender-adjusted)
```

The exponential term `e^(b × ΔHR_ratio)` captures the fact that the physiological cost of exercise rises steeply as intensity approaches the lactate threshold — a given increase in HR is metabolically far more demanding at 90 % effort than at 60 %.

**Reference:** Banister, E. W. (1991). Modeling elite athletic performance. In H. Green, J. McDougal, & H. Wenger (Eds.), *Physiological Testing of Elite Athletes* (pp. 403–424). Human Kinetics. See also the Polar Training Load Pro white paper for the exact implementation.

### Fallback path — simplified TRIMP approximation

When Polar's value is unavailable (e.g. for devices or sports where Training Load Pro is not recorded), a simplified TRIMP approximation is used:

```
intensity = avg_hr_bpm / max_hr_bpm   (relative HR intensity, 0–1)
load      = minutes × intensity × 2
```

This preserves the core TRIMP insight — load is a product of duration and intensity — while substituting peak session HR for the resting/maximal HR ratio used in the full formula. The scale factor of 2 is calibrated so that 60 minutes at 80 % of peak HR yields approximately 96 AU, consistent with Polar's output for a moderate aerobic run.

### Duration-only floor

When no HR data is available at all, load defaults to 1 AU per minute of exercise — a conservative floor that prevents rest days from being confused with training days while acknowledging the session occurred.

---

## Daily Training Load

```
daily_load = Σ estimate_session_load(s)  for all sessions on the day
```

---

## Acute / Chronic Workload Ratio (ACWR)

The ACWR quantifies how much the current week's load differs from the athlete's longer-term baseline. It is the primary injury-risk indicator.

### Primary path — Polar cardio-load endpoint

When the daily cardio-load data is available (synced via `GET /v3/users/cardio-load`):

```
ACWR = strain / tolerance
     = (7-day rolling mean of daily cardio_load)
       / (28-day rolling mean of daily cardio_load)
```

Polar pre-computes these rolling means, so this path is always preferred when the data is present.

### Fallback path — local rolling window

When Polar's rolling means are unavailable (e.g. account not synced recently, or missing API data):

```
acute_load   = mean( daily_loads[–7:]  )   # last 7 days
chronic_load = mean( daily_loads[–28:] )   # last 28 days
ACWR         = acute_load / chronic_load
```

Returns `None` when:
- Fewer than 28 days of history exist.
- The chronic load is effectively zero (< 0.1 PLU), to avoid division by near-zero.

### Interpretation

| ACWR Range | Interpretation |
|---|---|
| < 0.8 | Under-training relative to chronic load; potential de-training |
| 0.8 – 1.3 | Sweet spot — optimal training progression |
| 1.3 – 1.5 | Elevated load; monitor recovery carefully |
| > 1.5 | High acute-on-chronic spike — elevated soft-tissue injury risk |

**Reference:** Gabbett, T. J. (2016). The training–injury prevention paradox: should athletes be training smarter *and* harder? *British Journal of Sports Medicine*, 50(5), 273–280.

---

## Strain Score (0–100)

The strain score maps daily training load to a 0–100 scale using a hyperbolic tangent (tanh) normalization, with an optional ACWR-based modifier that elevates the score when the athlete is spiking load above their chronic baseline.

### Formula

```
base_score    = 100 × tanh( daily_load / 200 )

if ACWR > 1.5:
    modifier = min( (ACWR – 1.5) × 10,  10 )
else:
    modifier = 0

strain_score  = clamp( base_score + modifier,  0,  100 )
```

### Why tanh?

`tanh` is a smooth, bounded function that grows steeply at low loads (small efforts are meaningfully distinguished) and saturates at high loads (prevents a single extreme session from generating an unrealistically high score).

| Daily Load (PLU) | Base Score |
|---|---|
| 50 | ~24 |
| 100 | ~46 |
| 150 | ~64 |
| 200 | ~76 |
| 300 | ~90 |
| 400 | ~96 |

The **200 PLU reference** was chosen so that a typical hard training day (150–250 PLU in Polar's system) scores in the 60–80 range, leaving headroom for extreme sessions without saturation.

### ACWR Modifier

When `ACWR > 1.5`, up to **+10 points** are added to reflect the elevated injury risk of an acute load spike. The modifier scales linearly from 0 at ACWR = 1.5 to a cap of 10 at ACWR ≥ 2.5.

---

## Stored Fields

After analytics, the following values are stored in `strain_metrics`:

| Field | Unit | Description |
|---|---|---|
| `strain_score` | 0–100 | Composite daily strain score |
| `cardio_load` | AU | Daily cardio load (sum of sessions' TRIMP values) |
| `muscle_load` | AU | Daily muscle load (sum of sessions, if available) |
| `acute_load` | AU | 7-day acute rolling mean used for ACWR |
| `chronic_load` | AU | 28-day chronic rolling mean used for ACWR |
| `acwr` | ratio | Acute/Chronic Workload Ratio |
| `session_count` | integer | Number of training sessions that day |

---

## References

- Banister, E. W. (1991). Modeling elite athletic performance. In H. Green, J. McDougal, & H. Wenger (Eds.), *Physiological Testing of Elite Athletes* (pp. 403–424). Human Kinetics. *(Original TRIMP formulation — basis for Polar Training Load Pro cardio load)*
- Morton, R. H., Fitz-Clarke, J. R., & Banister, E. W. (1990). Modeling human performance in running. *Journal of Applied Physiology*, 69(3), 1171–1177.
- Polar Electro. *Training Load Pro — White Paper.* https://www.polar.com/img/static/whitepapers/pdf/polar-training-load-pro-white-paper.pdf
- Gabbett, T. J. (2016). The training–injury prevention paradox: should athletes be training smarter *and* harder? *British Journal of Sports Medicine*, 50(5), 273–280. https://doi.org/10.1136/bjsports-2015-095788
- Hulin, B. T. et al. (2016). Spikes in acute workload are associated with increased injury risk in elite cricket fast bowlers. *British Journal of Sports Medicine*, 48(8), 708–712.
