# Calculator.htm Methodology Report

This document reverse-engineers `Calculator.htm` ("Tinman's Running Calculator", attributed in-file to Tom Schwartz, dated February 18, 2012) to document exactly how it turns one race performance into training paces and equivalent-performance tables. The file is a spreadsheet exported to HTML/JavaScript (cell names like `p1C12` map 1:1 to an original Excel sheet, column C row 12), so the "methodology" is literally a set of spreadsheet formulas compiled into the `calc()` function. This report traces those formulas back to their inputs and expresses them in plain math, as a spec for reimplementation.

## 1. Inputs

| Field | Cell | Meaning |
|---|---|---|
| Distance value | `p1B4` | Numeric race distance |
| Distance unit | `p1B5` | One of Kilometers / Meters / Mile / Yards |
| Hours | `p1B6` | Race time — hours |
| Minutes | `p1B7` | Race time — minutes |
| Seconds | `p1B8` | Race time — seconds |

Everything else on the page is derived from these five values.

## 2. Normalization

- **Distance → kilometers.** The unit dropdown is looked up in a small table (Kilometers→1, Meters→1000, Mile→0.621371192, Yards→1092.777…) and the input distance is divided by that factor to get `distance_km`.
- **Time → decimal minutes.** `time_min = hours*60 + minutes + seconds/60`.
- **Raw pace.** `raw_pace_per_km = time_min / distance_km` (minutes per km, unadjusted).

## 3. Raw "Race-Splits" table (top of page, next to the inputs)

The small 200m/300m/400m/600m/800m/1200m/1600m/1‑mile table shown right next to the input boxes is **not** physiologically modeled — it's the raw input pace applied evenly:

```
split(distance_km) = raw_pace_per_km * distance_km
```
using fractions 0.2, 0.3, 0.4, 0.6, 0.8, 1.2, 1.6, and 1.609344 (miles) km. This is just "what would each split look like if you ran the goal race dead-even," not a training pace.

## 4. The core model: three distance-regime fatigue curves

Everything downstream (training paces and equivalent performances) depends on converting the single input performance into one normalized "quality" reference. The calculator does **not** use one formula across all distances — a single log or power-law curve is known to break down at the extremes (sprints vs. ultras), so it picks between three regimes based on the input distance:

| Regime | Condition on `distance_km` | Model |
|---|---|---|
| Long / aerobic | `>= 3` | Logarithmic decay |
| Middle / transition | `0.8 < distance_km < 3` | Power law |
| Short / anaerobic | `<= 0.8` | Cubic polynomial |

**Long-distance (≥3km) branch:**
```
decay = 1 - 0.056 * ln(time_min / 6.6)
adjusted_time = time_min * decay
adjusted_pace_per_km = adjusted_time / distance_km
```

**Middle-distance (0.8–3km) branch** — a power-law fit instead of the log curve:
```
x = 3 / distance_km
ratio = 1.01751 * x ^ (-1.12473)
adjusted_pace_per_km = raw_pace_per_km / ratio
```

**Short-distance (≤0.8km) branch** — a cubic polynomial fit (log/power curves are unreliable at sprint distances):
```
x = 3 / distance_km
cubic = -0.0005*x^3 + 0.0225*x^2 + 1.3743*x - 1.1024
adjusted_pace_per_km = raw_pace_per_km * cubic   # (via the same velocity pipeline below)
```

All three branches converge on the same downstream quantity: a fatigue-adjusted pace expressed **as if for a 3 km effort**. (The reference distance 3 km / reference time 6.6 min recur throughout the sheet — 3 km is this calculator's internal "anchor" distance, and 3000 m is exactly the distance whose equivalent-performance multiplier equals 1, see §6.)

## 5. Linearizing pace into a VO2-like domain for percentage scaling

Training-zone percentages (58%, 66%, ... 130%) cannot be applied directly to *pace*, because pace and effort/oxygen cost are not linearly related. So the calculator converts the regime-adjusted pace to velocity (m/min), then into a linear "VO2-like" unit via its own economy approximation:

```
velocity_m_per_min = 1000 / adjusted_pace_per_km
vo2_like = 0.22 * velocity_m_per_min - 5.6
```

This is the calculator's own linear running-economy approximation — structurally similar to published velocity↔VO2 running-economy equations (e.g. ACSM's `VO2 = 0.2*v + 3.5`), but with its own fitted slope/intercept; it is not a verified transcription of a specific published formula.

The regime selection happens twice with parallel formula chains — once feeding the equivalent-performance table (§6), once feeding this VO2-linearization for training zones (§7) — but both ultimately represent the same fatigue-adjusted 3 km-equivalent effort.

## 6. Equivalent-performance table

The reference value (call it `Q`, in day-fraction units — i.e. `time_min/1440` — internally `c1E41`/`c1R4`) is the single number selected from whichever of the three regime branches applied to the *input* distance. Every value in the "Equivalent Performances" tables (metric and imperial, 100 m through 100 km/100 mi) is simply:

```
predicted_time(target_distance) = Q * multiplier[target_distance]
```

The `multiplier` table is **pre-baked** into the sheet (not recomputed live from the three-regime model per target distance). This means the calculator assumes one universal "how pace degrades with distance" shape for every athlete, and only the overall magnitude (`Q`, from your one input performance) is athlete-specific. The full multiplier table, extracted from the code:

**Metric** (multiplier relative to `Q`; 3000 m is the reference point, multiplier = 1):

| Distance | Multiplier | Distance | Multiplier |
|---|---|---|---|
| 100 m | 0.021332605 | 3200 m | 1.070536 |
| 200 m | 0.043692735 | 3000 m Steeplechase | 1.070535751 |
| 400 m | 0.097470281 | 4000 m | 1.355165312 |
| 600 m | 0.15951253 | 5000 m | 1.71574775 |
| 800 m | 0.2292 | 6000 m | 2.080767578 |
| 1000 m | 0.295737296 | 8000 m | 2.821649842 |
| 1200 m | 0.363047642 | 10 km | 3.574323047 |
| 1500 m | 0.46662 | 12 km | 4.336666168 |
| 1600 m | 0.501748364 | 15 km | 5.495281616 |
| 2000 m | 0.644886914 | 20 km | 7.459113311 |
| 2400 m | 0.791664348 | 25 km | 9.456101224 |
| **3000 m** | **1 (reference)** | 30 km | 11.48032823 |
| | | Marathon | 16.5091191 |
| | | 50 km | 19.78359126 |
| | | 100 km | 41.47831583 |

**Imperial** (multiplier relative to the same `Q`; Marathon reuses the metric Marathon value exactly, since it's a fixed distance):

| Distance | Multiplier | Distance | Multiplier |
|---|---|---|---|
| 100 yd | 0.019795455 | 4 miles | 2.241636505 |
| 220 yd | 0.044016963 | 5 miles | 2.839107886 |
| 440 yd | 0.098237362 | 6 miles | 3.444150843 |
| 880 yd | 0.23057 | 10 miles | 5.921509071 |
| 1000 yd | 0.267650565 | Half-Marathon | 7.894858267 |
| 1 mile | 0.505045258 | 20 miles | 12.37316866 |
| 1.5 miles | 0.796866225 | Marathon | = metric Marathon (16.5091191) |
| 2 miles | 1.077140198 | 50 miles | 32.87853761 |
| 3 miles | 1.653401007 | 100 miles | 69.04212928 |

## 7. Training-zone pace table

The zone table (rows: Very Easy, Easy, Moderate, Tempo, Threshold, CV, AP, V.O2 max, 110%, 120%, 130%; columns: Mile, 1600m, 1200m, 1000m, 800m, 600m, 400m, 300m, 200m) is generated from the same `vo2_like` value from §5:

```
for each zone percentage p in {58,66,74,82,87,90,95,100,110,120,130}:
    target_vo2_like = vo2_like * (p / 100)
    target_velocity  = (target_vo2_like + 5.6) / 0.22
    target_pace_per_km = 1000 / target_velocity
```

then each `target_pace_per_km` is scaled to the 9 display distances by simple proportion (1.609344, 1.6, 1.2, 1.0, 0.8, 0.6, 0.4, 0.3, 0.2 — same fraction table as §3, applied here to the *adjusted* pace instead of the raw one). Zone-label-to-percentage mapping, as read directly off the page:

| Label | % |
|---|---|
| Very Easy | 58% |
| Easy | 66% |
| Moderate | 74% |
| Tempo | 82% |
| Threshold | 87% |
| CV | 90% |
| AP | 95% |
| V.O2 max | 100% |
| 110% | 110% |
| 120%| 120% |
| 130% | 130% |

## 8. Summary of the full pipeline

```
distance, time  →  normalize to km / decimal minutes
              →  pick regime (long ≥3km / middle 0.8–3km / short ≤0.8km)
              →  apply that regime's fatigue curve → adjusted 3km-equivalent time (Q)
      Q ─────┬─→ × pre-baked per-distance multiplier → Equivalent Performances tables
             └─→ → velocity → linear VO2-like unit → × zone% → invert
                                                     → Training Pace table (9 distances × 11 zones)
```

## 9. Notes / limitations for reimplementation

- **The three regime-switch thresholds (0.8 km and 3 km) and their distinct formulas must be reproduced exactly** — plugging a 200 m input into the long-distance log-decay formula (or vice versa) will silently produce wrong numbers rather than erroring.

- The `0.22 / -5.6` velocity→VO2-like linear transform and the `0.056`/`1.01751`/`-1.12473`/cubic-polynomial coefficients are the calculator's own fitted constants; they resemble published running-economy/performance-equivalency concepts (Riegel-style power laws, VO2-linear economy models) in *structure* but are not confirmed to be verbatim transcriptions of any specific published formula — treat them as this calculator's own curve fit, sourced only from the code itself.
