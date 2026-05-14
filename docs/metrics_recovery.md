# Recovery & Readiness Metrics

This page describes every signal and formula used to compute the Polar Dashboard recovery score: what each input represents, how it is normalised, and how the contributors are weighted into a single readiness index.

---

## Input Data

Recovery data is assembled from three sources.

### Overnight Physiological Measurements (Polar Nightly Recharge)

Recorded during sleep by the Polar device; retrieved via the sleep session endpoint.

| Field | Unit | Description |
|---|---|---|
| `rmssd_ms` | ms | Root mean square of successive PPI (pulse-to-pulse interval) differences, measured overnight. Primary HRV metric — reflects parasympathetic (rest-and-digest) activity |
| `resting_hr_bpm` | bpm | Mean heart rate during the overnight rest window |
| `mean_skin_temperature_celsius` | °C | Mean wrist skin temperature during sleep |
| `nightly_recharge_score` | 0–100 | Polar's proprietary ANS (autonomic nervous system) recharge score, derived from overnight HRV, HR, and breathing rate |

### Previous Day's Training Load

| Field | Unit | Description |
|---|---|---|
| `previous_strain_score` | 0–100 | Strain score of the preceding day (computed by the strain analytics pipeline) |
| `chronic_load` (tolerance) | Polar Load Units | Polar's 28-day rolling cardio load mean — a proxy for current aerobic fitness level |

### Sleep Quality

| Field | Unit | Description |
|---|---|---|
| `sleep_score` | 0–100 | Composite sleep quality score for the preceding night (see Sleep Metrics documentation) |

---

## Personal Baselines and Z-Score Normalisation

HRV and resting HR are highly individual — a "good" RMSSD of 60 ms for one athlete may be baseline for another. All physiological signals are therefore normalised against a **personal rolling baseline** rather than a population reference.

### Rolling Baseline Computation

For each signal (RMSSD, resting HR, Polar tolerance):

```
baseline = rolling_mean( values, window=30 days )
std      = rolling_std(  values, window=30 days )
z_score  = (today_value – baseline) / std
```

- Window: **30 days** (requires at least 2 data points; returns `None` otherwise).
- The baseline and standard deviation are recomputed each time the analytics pipeline runs, using the available history up to the day being scored.

### Z-Score to Contributor (0–100)

All z-score-based contributors are mapped to a 0–100 scale using:

```
contributor = ((clamp(z, –3, +3) + 3) / 6) × 100
```

- `z = +3` → 100 (well above personal baseline — excellent)
- `z = 0`  → 50 (at personal baseline — neutral)
- `z = –3` → 0 (well below personal baseline — concerning)

The clamp at ±3 standard deviations ensures extreme outliers (e.g. from illness) do not dominate the score.

**For resting HR the direction is inverted** (lower HR = better recovery):

```
hr_contributor = 100 – ((clamp(z, –3, +3) + 3) / 6) × 100
```

---

## The Seven Contributors

### 1. Sleep Quality (weight: 35 %)

```
sleep_contributor = sleep_score   (0–100, from sleep analytics)
```

The preceding night's composite sleep score is the largest single driver of next-day readiness. Missing → neutral 50.

### 2. HRV — RMSSD Z-Score (weight: 25 %)

```
z = (RMSSD_today – 30d_mean_RMSSD) / 30d_std_RMSSD
hrv_contributor = z_to_pct(z)
```

RMSSD above the personal baseline indicates stronger parasympathetic tone and better autonomic recovery. Missing → neutral 50.

**Reference:** Buchheit, M. (2014). Monitoring training status with HR measures: do all roads lead to Rome? *Frontiers in Physiology*, 5, 73.

### 3. Resting HR Z-Score (weight: 20 %)

```
z = (resting_HR_today – 30d_mean_resting_HR) / 30d_std_resting_HR
hr_contributor = z_to_pct(z, invert=True)
```

Resting HR below the personal baseline indicates a well-recovered cardiovascular system. Missing → neutral 50.

**Reference:** Plews, D. J. et al. (2013). Heart rate variability in elite triathletes, is variation in variability the key to effective training? A case comparison. *European Journal of Applied Physiology*, 113(3), 831–841.

### 4. Previous Strain (weight: 10 %)

```
strain_contributor = max( 0,  100 – previous_strain_score )
```

High training load the day before reduces today's readiness (the score is simply the inverse of strain). A rest day (strain = 0) contributes a full 100; a maximal effort day (strain = 100) contributes 0. Missing → neutral 50.

### 5. Nightly Recharge (weight: 4 %)

```
recharge_contributor = nightly_recharge_score   (0–100, Polar ANS recharge)
```

Polar's nightly recharge score integrates overnight HRV, heart rate, and respiratory rate into a proprietary ANS recovery index. It is used here at a lower weight since RMSSD and resting HR already capture the same physiological signal more transparently. Missing → neutral 50.

### 6. Skin Temperature Deviation (weight: 4 %)

```
temperature_contributor = clamp( 50 – deviation_celsius × 50,  0,  100 )
```

Where `deviation_celsius = mean_skin_temp_today – 30d_rolling_mean_skin_temp`.

- 0 °C deviation → 50 (neutral, no thermal stress)
- +1 °C above baseline → 0 (strong signal of illness, inflammation, or overheating)
- Negative deviations → above 50 (slightly cooler skin, often benign — capped at 100)

Skin temperature is sourced directly from the device sensor when available. Missing → neutral 50.

**Reference:** Kräuchi, K., & Wirz-Justice, A. (1994). Circadian clues to sleep onset mechanisms. *Neuropsychopharmacology*, 10(3), 223S–226S.

### 7. Aerobic Fitness Load Z-Score (weight: 2 %)

```
z = (tolerance_today – 30d_mean_tolerance) / 30d_std_tolerance
fitness_contributor = z_to_pct(z)
```

Where `tolerance` is Polar's 28-day rolling cardio load (the chronic load from `GET /v3/users/cardio-load`). A rising tolerance indicates improving aerobic fitness and a higher capacity to absorb training stress, which marginally boosts readiness. Missing → neutral 50.

This is a low-weight (2 %) contextual signal: it represents aerobic capacity trend rather than acute day-to-day recovery state.

---

## Composite Recovery Score

```
recovery_score =   0.35 × sleep_contributor
                 + 0.25 × hrv_contributor
                 + 0.20 × hr_contributor
                 + 0.10 × strain_contributor
                 + 0.04 × recharge_contributor
                 + 0.04 × temperature_contributor
                 + 0.02 × fitness_contributor
```

All seven weights sum to **1.00** (100 %).

Missing contributors default to **50 (neutral)**, so the score remains interpretable even when only partial data is available (e.g. no skin temperature sensor, or insufficient baseline history for z-scores).

### Interpretation Zones

| Score | Zone | Meaning |
|---|---|---|
| 67 – 100 | Optimal | Good readiness — proceed with planned training |
| 34 – 66 | Fair | Moderate readiness — reduce intensity or volume if fatigued |
| 0 – 33 | Low | Poor readiness — prioritise rest and recovery |

---

## Confidence and Missing Data

The score is always computable, but its reliability depends on how many contributors have real data. Track which fields are `None` in the `RecoveryContributors` to assess confidence:

- **Full data** (all 7 contributors present): high confidence
- **Partial data** (e.g. missing temperature or fitness z-score): moderate confidence; the score still reflects the available signals
- **Minimal data** (only sleep score available): the score is dominated by sleep quality and baseline signals at neutral — use with caution

---

## References

- Buchheit, M. (2014). Monitoring training status with HR measures: do all roads lead to Rome? *Frontiers in Physiology*, 5, 73. https://doi.org/10.3389/fphys.2014.00073
- Plews, D. J., Laursen, P. B., Stanley, J., Buchheit, M., & Kilding, A. E. (2013). Heart rate variability in elite triathletes, is variation in variability the key to effective training? A case comparison. *European Journal of Applied Physiology*, 113(3), 831–841.
- Kiviniemi, A. M. et al. (2007). Endurance performance and nonutility of heart rate variability monitoring without feedback. *Medicine & Science in Sports & Exercise*, 39(12), 2219–2226.
- Gabbett, T. J. (2016). The training–injury prevention paradox: should athletes be training smarter *and* harder? *British Journal of Sports Medicine*, 50(5), 273–280.
- Malik, M. et al. (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology. *Circulation*, 93(5), 1043–1065.
