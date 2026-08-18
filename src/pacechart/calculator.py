"""Training-pace and equivalent-performance calculator.

Implemented from ``Calculator-Methodology.md`` (sections referenced in
comments below), not from ``Calculator.htm`` itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log

# --- Section 2: unit normalization -----------------------------------------

# Divide an input distance by this factor to get kilometers.
UNITS_PER_KM = {
    "kilometers": 1.0,
    "meters": 1000.0,
    "mile": 0.621371192,
    "yards": 1092.777778,
}

# --- Section 3 / 7: distance fractions (km) for the 9 display distances ----

DISPLAY_DISTANCES_KM = {
    "Mile": 1.609344,
    "1600m": 1.6,
    "1200m": 1.2,
    "1000m": 1.0,
    "800m": 0.8,
    "600m": 0.6,
    "400m": 0.4,
    "300m": 0.3,
    "200m": 0.2,
}

# --- Section 4: regime thresholds and fatigue-curve constants --------------

LONG_THRESHOLD_KM = 3.0
SHORT_THRESHOLD_KM = 0.8

LONG_DECAY_COEFF = 0.056
LONG_DECAY_REF_TIME_MIN = 6.6

MID_POWER_COEFF = 1.01751
MID_POWER_EXPONENT = -1.12473
MID_REF_DISTANCE_KM = 3.0

SHORT_CUBIC_A = -0.0005
SHORT_CUBIC_B = 0.0225
SHORT_CUBIC_C = 1.3743
SHORT_CUBIC_D = -1.1024
SHORT_REF_DISTANCE_KM = 3.0

# --- Section 5: pace <-> VO2-like linearization -----------------------------

VO2_SLOPE = 0.22
VO2_INTERCEPT = -5.6

# --- Section 6: equivalent-performance multipliers (relative to Q) ---------
# Q is the fatigue-adjusted time for a 3000m-equivalent effort, in day
# fractions (see `reference_quantity`). predicted_time = Q * multiplier.

EQUIVALENT_PERFORMANCES_METRIC = {
    "100m": 0.021332605,
    "200m": 0.043692735,
    "400m": 0.097470281,
    "600m": 0.15951253,
    "800m": 0.2292,
    "1000m": 0.295737296,
    "1200m": 0.363047642,
    "1500m": 0.46662,
    "1600m": 0.501748364,
    "2000m": 0.644886914,
    "2400m": 0.791664348,
    "3000m": 1.0,
    "3200m": 1.070536,
    "3000m Steeplechase": 1.070535751,
    "4000m": 1.355165312,
    "5000m": 1.71574775,
    "6000m": 2.080767578,
    "8000m": 2.821649842,
    "10km": 3.574323047,
    "12km": 4.336666168,
    "15km": 5.495281616,
    "20km": 7.459113311,
    "25km": 9.456101224,
    "30km": 11.48032823,
    "Marathon": 16.5091191,
    "50km": 19.78359126,
    "100km": 41.47831583,
}

EQUIVALENT_PERFORMANCES_IMPERIAL = {
    "100 yd": 0.019795455,
    "220 yd": 0.044016963,
    "440 yd": 0.098237362,
    "880 yd": 0.23057,
    "1000 yd": 0.267650565,
    "1 mile": 0.505045258,
    "1.5 miles": 0.796866225,
    "2 miles": 1.077140198,
    "3 miles": 1.653401007,
    "4 miles": 2.241636505,
    "5 miles": 2.839107886,
    "6 miles": 3.444150843,
    "10 miles": 5.921509071,
    "Half-Marathon": 7.894858267,
    "20 miles": 12.37316866,
    "Marathon": 16.5091191,  # same fixed distance as the metric Marathon
    "50 miles": 32.87853761,
    "100 miles": 69.04212928,
}

# --- Section 7: training zones ----------------------------------------------

TRAINING_ZONES = {
    "Very Easy": 58,
    "Easy": 66,
    "Moderate": 74,
    "Tempo": 82,
    "Threshold": 87,
    "CV": 90,
    "AP": 95,
    "V.O2 max": 100,
    "110%": 110,
    "120%": 120,
    "130%": 130,
}


class Regime:
    LONG = "long"
    MIDDLE = "middle"
    SHORT = "short"


@dataclass(frozen=True)
class Performance:
    """A single race performance: a distance covered in a time."""

    distance_km: float
    time_min: float

    def __post_init__(self) -> None:
        if self.distance_km <= 0:
            raise ValueError("distance_km must be positive")
        if self.time_min <= 0:
            raise ValueError("time_min must be positive")


def normalize(distance_value: float, unit: str, hours: float, minutes: float, seconds: float) -> Performance:
    """Section 2: convert raw distance+unit and h/m/s into a Performance."""
    key = unit.strip().lower()
    if key not in UNITS_PER_KM:
        raise ValueError(f"Unknown distance unit: {unit!r}")
    distance_km = distance_value / UNITS_PER_KM[key]
    time_min = hours * 60 + minutes + seconds / 60
    return Performance(distance_km=distance_km, time_min=time_min)


def raw_pace_per_km(perf: Performance) -> float:
    """Section 2: unadjusted pace, minutes per km."""
    return perf.time_min / perf.distance_km


def race_splits(perf: Performance) -> dict[str, float]:
    """Section 3: even-pace splits of the raw (unadjusted) performance, in minutes."""
    pace = raw_pace_per_km(perf)
    return {label: pace * km for label, km in DISPLAY_DISTANCES_KM.items()}


def regime_for(distance_km: float) -> str:
    """Section 4: pick which of the three fatigue-curve regimes applies."""
    if distance_km >= LONG_THRESHOLD_KM:
        return Regime.LONG
    if distance_km <= SHORT_THRESHOLD_KM:
        return Regime.SHORT
    return Regime.MIDDLE


def adjusted_pace_per_km(perf: Performance) -> float:
    """Section 4: fatigue-adjusted pace, expressed as if for a 3km effort.

    Selects one of three regimes by input distance and applies that
    regime's fatigue curve to the raw pace.
    """
    regime = regime_for(perf.distance_km)
    pace = raw_pace_per_km(perf)

    if regime == Regime.LONG:
        decay = 1 - LONG_DECAY_COEFF * log(perf.time_min / LONG_DECAY_REF_TIME_MIN)
        adjusted_time = perf.time_min * decay
        return adjusted_time / perf.distance_km

    if regime == Regime.MIDDLE:
        x = MID_REF_DISTANCE_KM / perf.distance_km
        ratio = MID_POWER_COEFF * x**MID_POWER_EXPONENT
        return pace / ratio

    # Regime.SHORT
    x = SHORT_REF_DISTANCE_KM / perf.distance_km
    cubic = SHORT_CUBIC_A * x**3 + SHORT_CUBIC_B * x**2 + SHORT_CUBIC_C * x + SHORT_CUBIC_D
    return pace * cubic


def reference_quantity(perf: Performance) -> float:
    """Section 6: Q, the fatigue-adjusted 3000m-equivalent time as a day fraction.

    Derived from `adjusted_pace_per_km`: that pace is "as if for a 3km
    effort" (Section 4), and Q is defined so that the 3000m equivalent
    performance is exactly `Q * 1` (Section 6's multiplier table gives
    3000m a multiplier of 1). So Q = (adjusted pace * 3km) / 1440 min/day.
    """
    pace = adjusted_pace_per_km(perf)
    adjusted_3k_time_min = pace * 3.0
    return adjusted_3k_time_min / 1440.0


def equivalent_performances(perf: Performance) -> dict[str, float]:
    """Section 6: predicted times (minutes) at every tabulated distance."""
    q = reference_quantity(perf)
    results: dict[str, float] = {}
    for label, multiplier in EQUIVALENT_PERFORMANCES_METRIC.items():
        results[label] = q * multiplier * 1440.0
    for label, multiplier in EQUIVALENT_PERFORMANCES_IMPERIAL.items():
        results[label] = q * multiplier * 1440.0
    return results


def vo2_like(perf: Performance) -> float:
    """Section 5: linearize the regime-adjusted pace into a VO2-like unit."""
    pace = adjusted_pace_per_km(perf)
    velocity_m_per_min = 1000.0 / pace
    return VO2_SLOPE * velocity_m_per_min + VO2_INTERCEPT


def training_paces(perf: Performance) -> dict[str, dict[str, float]]:
    """Section 7: minutes for every (zone, display distance) combination."""
    base_vo2 = vo2_like(perf)
    paces: dict[str, dict[str, float]] = {}
    for zone_label, pct in TRAINING_ZONES.items():
        target_vo2 = base_vo2 * (pct / 100.0)
        target_velocity = (target_vo2 - VO2_INTERCEPT) / VO2_SLOPE
        target_pace_per_km = 1000.0 / target_velocity
        paces[zone_label] = {
            dist_label: target_pace_per_km * km
            for dist_label, km in DISPLAY_DISTANCES_KM.items()
        }
    return paces


def format_minutes(total_minutes: float, decimals: int = 2) -> str:
    """Format a minutes value as H:MM:SS(.d..) or M:SS(.d..).

    Rounds `total_seconds` before splitting into hours/minutes/seconds so
    that e.g. 59.96s at decimals=1 carries into "1:00.0" rather than the
    unrepresentable "0:60.0".
    """
    total_seconds = round(total_minutes * 60.0, decimals)
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds - hours * 3600 - minutes * 60
    width = 2 if decimals == 0 else decimals + 3
    seconds_str = f"{seconds:0{width}.{decimals}f}"
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds_str}"
    return f"{minutes}:{seconds_str}"
