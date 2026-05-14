# Sleep Metrics

This page describes every sleep metric computed by the Polar Dashboard, including the raw inputs from the Polar API, the scoring formulas, and the physiological rationale.

---

## Input Data

Sleep sessions are recorded by the Polar device during the night and retrieved via the Polar AccessLink v3 API (`GET /v3/users/sleep`).

| Field | Unit | Description |
|---|---|---|
| `duration_seconds` | seconds | Total time in bed (session start → end, includes awake periods) |
| `total_sleep_seconds` | seconds | Time spent asleep (light + deep + REM), derived from stage data |
| `sleep_efficiency_pct` | % (0–100) | Fraction of time in bed spent asleep: `total_sleep / time_in_bed * 100` |
| `sleep_latency_seconds` | seconds | Time elapsed between lights-out and first sleep onset |
| `deep_sleep_seconds` | seconds | Slow-wave (N3) sleep duration |
| `rem_sleep_seconds` | seconds | REM sleep duration |
| `light_sleep_seconds` | seconds | Light (N1/N2) sleep duration |
| `awake_seconds` | seconds | Time spent awake after initial sleep onset |
| `unknown_sleep_seconds` | seconds | Unclassified time (device could not determine stage) |
| `short_interruption_duration_seconds` | seconds | Cumulative duration of brief awakenings (< 5 min) |
| `long_interruption_duration_seconds` | seconds | Cumulative duration of prolonged awakenings (≥ 5 min) |
| `rmssd_ms` | ms | Root mean square of successive PPI (pulse-to-pulse interval) differences, recorded overnight — primary overnight HRV metric |
| `average_hr_bpm` | bpm | Mean heart rate across the entire sleep session |
| `continuity_score` | 20–100 | Polar sleep continuity estimate, scaled from Polar's raw 1.0–5.0 scale (× 20). Reflects how uninterrupted the sleep was: 5.0 (→ 100) = completely uninterrupted; 1.0 (→ 20) = highly fragmented |

---

## Sleep Score (Composite, 0–100)

The composite sleep score aggregates four independent dimensions into a single 0–100 value.

### Formula

```
sleep_score = 0.35 × duration_score
            + 0.35 × efficiency_score
            + 0.20 × architecture_score
            + 0.10 × continuity_score
```

Missing sub-scores are replaced by a neutral value of **50**, so the composite degrades gracefully when data is unavailable. The continuity contributor ranges 20–100 (not 0–100) because Polar's raw 1.0–5.0 scale does not reach zero.

---

### Duration Score (35 %)

A Gaussian (bell-curve) centred on the evidence-based optimal of **7.5 hours**, with a standard deviation of 1.5 hours. Both short and excessively long sleep are penalised symmetrically.

```
hours  = total_sleep_seconds / 3600

duration_score = 100 × exp( –(hours – 7.5)² / (2 × 1.5²) )
```

Example values:

| Hours slept | Score |
|---|---|
| 4.5 h | ~13 |
| 6.0 h | ~60 |
| 7.5 h | 100 |
| 9.0 h | ~60 |
| 10.5 h | ~13 |

**Rationale:** The 7–9 hour recommendation for adults is supported by Walker (2017) and the National Sleep Foundation. The Gaussian shape reflects that both deprivation and excess sleep are associated with negative health outcomes.

---

### Efficiency Score (35 %)

Sleep efficiency measures how much of the time in bed is spent actually sleeping.

```
efficiency_score = min( efficiency_pct / 90 × 100,  100 )
```

- Target efficiency: **90 %** (clinical threshold for healthy sleep; values above 90 are capped at 100).
- Returns **50** (neutral) when efficiency data is absent.

---

### Architecture Score (20 %)

Sleep architecture reflects the quality of stage composition. All percentages are expressed as a fraction of **time in bed** (not total sleep time), so that DEEP + REM + LIGHT + AWAKE ≈ 100 %.

Three sub-components are averaged (only available components contribute):

#### Deep Sleep Sub-score

```
deep_pct   = deep_sleep_seconds / time_in_bed × 100
deep_score = min( deep_pct / 17,  1.0 ) × 100
```

Target: **≥ 17 %** of time in bed. Deep (slow-wave) sleep drives physical restoration, memory consolidation, and growth hormone secretion.

#### REM Sleep Sub-score

```
rem_pct   = rem_sleep_seconds / time_in_bed × 100
rem_score = min( rem_pct / 20,  1.0 ) × 100
```

Target: **≥ 20 %** of time in bed. REM sleep is critical for emotional regulation and declarative memory consolidation.

#### Interruption Penalty

```
awake_pct = awake_seconds / time_in_bed × 100

interruption_score = max( 0,  100 – awake_pct / 15 × 100 )
```

- 0 % awake time → 100 (no fragmentation)
- ≥ 15 % awake time → 0 (heavily fragmented)

**Architecture score** = mean of whichever sub-scores have data. Returns **50** when no stage data is available.

---

### Continuity Score (10 %)

Polar defines continuity as an estimate of how uninterrupted the sleep was, on a scale of **1.0 to 5.0**, where 5.0 means no interruptions and lower values indicate increasingly fragmented sleep.

During ingestion this raw value is scaled to align with the 0–100 contributor range used by the other sub-scores:

```
continuity_score = polar_continuity × 20
```

| Polar continuity | Scaled score | Interpretation |
|---|---|---|
| 5.0 | 100 | Completely uninterrupted |
| 4.0 | 80 | Minor interruptions |
| 3.0 | 60 | Moderate fragmentation |
| 2.0 | 40 | Significant fragmentation |
| 1.0 | 20 | Heavily fragmented |

The effective range after scaling is **20–100** (not 0–100), meaning even the most fragmented night still contributes a non-zero value. When absent the score defaults to **50** (neutral, roughly equivalent to a Polar continuity of 2.5).

---

## Sleep Consistency Score (0–100)

Consistency measures how stable the sleep schedule is across the past 7 nights, rewarding regular bedtimes, wake times, and durations.

### Formula

Three dimensions each contribute equally:

```
bed_score  = max( 0,  100 – σ(bedtimes_h) × 25 )
wake_score = max( 0,  100 – σ(waketimes_h) × 25 )
dur_score  = max( 0,  100 – σ(durations_h) × 25 )

consistency_score = (bed_score + wake_score + dur_score) / 3
```

Where `σ` is the population standard deviation in hours.

- **1 hour** of standard deviation costs **25 points** per dimension.
- Bedtimes crossing midnight are shifted: hours 0–5 → 24–29 so that 23:30 and 00:30 are numerically adjacent.
- Requires at least **2 sessions** (returns `None` if fewer than 2 nights are available).
- Window: the **7 most recent nights** including the current night.

**Rationale:** Irregular sleep timing (social jetlag) is associated with cardiometabolic risk and cognitive impairment independent of total sleep duration. Roenneberg et al. (2012). *Current Biology*, 22(10), 939–943.

---

## Stage Percentages in the Data Table

Stage percentages stored in the database are **always relative to time in bed**:

```
deep_pct  = deep_sleep_seconds  / time_in_bed × 100
rem_pct   = rem_sleep_seconds   / time_in_bed × 100
light_pct = light_sleep_seconds / time_in_bed × 100
awake_pct = awake_seconds       / time_in_bed × 100
```

This means they sum to approximately 100 % (small gaps may occur due to unknown/unclassified periods).

---

## References

- Walker, M. (2017). *Why We Sleep: Unlocking the Power of Sleep and Dreams.* Scribner.
- Hirshkowitz, M. et al. (2015). National Sleep Foundation's sleep time duration recommendations: methodology and results summary. *Sleep Health*, 1(1), 40–43.
- Roenneberg, T. et al. (2012). Social jetlag and obesity. *Current Biology*, 22(10), 939–943.
- Buysse, D. J. et al. (1989). The Pittsburgh Sleep Quality Index: a new instrument for psychiatric practice and research. *Psychiatry Research*, 28(2), 193–213.
- Dijk, D. J. (2009). Regulation and functional correlates of slow wave sleep. *Journal of Clinical Sleep Medicine*, 5(2 Suppl), S6–S15.
