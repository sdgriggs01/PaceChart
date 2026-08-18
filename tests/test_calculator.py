"""Tests for pacechart.calculator.

These check internal consistency of the formulas as specified in
Calculator-Methodology.md (unit conversions, regime boundaries, and
algebraic round-trips implied by the spec), not against numbers pulled
from Calculator.htm.
"""

import math

import pytest

from pacechart.calculator import (
    DISPLAY_DISTANCES_KM,
    TRAINING_ZONES,
    Performance,
    adjusted_pace_per_km,
    equivalent_performances,
    format_minutes,
    normalize,
    race_splits,
    raw_pace_per_km,
    reference_quantity,
    regime_for,
    training_paces,
)


def test_normalize_kilometers_is_identity():
    perf = normalize(5.0, "Kilometers", 0, 20, 0)
    assert perf.distance_km == pytest.approx(5.0)
    assert perf.time_min == pytest.approx(20.0)


def test_normalize_meters_to_km():
    perf = normalize(1000.0, "Meters", 0, 4, 0)
    assert perf.distance_km == pytest.approx(1.0)


def test_normalize_mile_to_km():
    perf = normalize(1.0, "Mile", 0, 4, 0)
    assert perf.distance_km == pytest.approx(1.609344, rel=1e-4)


def test_normalize_yards_to_km():
    perf = normalize(1092.777778, "Yards", 0, 4, 0)
    assert perf.distance_km == pytest.approx(1.0, rel=1e-4)


def test_normalize_time_components():
    perf = normalize(1.0, "Kilometers", 1, 2, 30)
    assert perf.time_min == pytest.approx(60 + 2 + 30 / 60)


def test_normalize_rejects_unknown_unit():
    with pytest.raises(ValueError):
        normalize(1.0, "Furlongs", 0, 4, 0)


def test_performance_rejects_non_positive_values():
    with pytest.raises(ValueError):
        Performance(distance_km=0, time_min=10)
    with pytest.raises(ValueError):
        Performance(distance_km=5, time_min=0)


@pytest.mark.parametrize(
    "distance_km,expected_regime",
    [
        (3.0, "long"),
        (10.0, "long"),
        (2.999999, "middle"),
        (1.5, "middle"),
        (0.800001, "middle"),
        (0.8, "short"),
        (0.4, "short"),
    ],
)
def test_regime_thresholds(distance_km, expected_regime):
    assert regime_for(distance_km) == expected_regime


def test_race_splits_are_even_pace_of_raw_performance():
    # Section 3: race-splits use the *raw*, unadjusted pace.
    perf = Performance(distance_km=5.0, time_min=20.0)
    pace = raw_pace_per_km(perf)
    splits = race_splits(perf)
    for label, km in DISPLAY_DISTANCES_KM.items():
        assert splits[label] == pytest.approx(pace * km)


def test_adjusted_pace_long_regime_matches_formula():
    perf = Performance(distance_km=5.0, time_min=20.0)
    decay = 1 - 0.056 * math.log(perf.time_min / 6.6)
    expected = (perf.time_min * decay) / perf.distance_km
    assert adjusted_pace_per_km(perf) == pytest.approx(expected)


def test_adjusted_pace_middle_regime_matches_formula():
    perf = Performance(distance_km=1.5, time_min=4.5)
    x = 3.0 / perf.distance_km
    ratio = 1.01751 * x ** (-1.12473)
    expected = raw_pace_per_km(perf) / ratio
    assert adjusted_pace_per_km(perf) == pytest.approx(expected)


def test_adjusted_pace_short_regime_matches_formula():
    perf = Performance(distance_km=0.4, time_min=1.0)
    x = 3.0 / perf.distance_km
    cubic = -0.0005 * x**3 + 0.0225 * x**2 + 1.3743 * x - 1.1024
    expected = raw_pace_per_km(perf) * cubic
    assert adjusted_pace_per_km(perf) == pytest.approx(expected)


def test_reference_quantity_gives_3000m_equivalent_at_multiplier_one():
    # Section 6: the 3000m multiplier is defined to be 1, i.e. the
    # predicted 3000m time is exactly Q expressed in minutes.
    perf = Performance(distance_km=5.0, time_min=20.0)
    q = reference_quantity(perf)
    predicted = equivalent_performances(perf)
    assert predicted["3000m"] == pytest.approx(q * 1440.0)


def test_equivalent_performances_marathon_uses_shared_multiplier():
    # Section 6: Marathon is a fixed distance regardless of unit system,
    # so both tables use the same multiplier (16.5091191).
    perf = Performance(distance_km=5.0, time_min=20.0)
    q = reference_quantity(perf)
    predicted = equivalent_performances(perf)
    assert predicted["Marathon"] == pytest.approx(q * 16.5091191 * 1440.0)


def test_training_paces_at_100_percent_round_trips_to_adjusted_pace():
    # Section 5/7: the VO2-like linearization and its inverse must be
    # exact inverses, so the 100% (V.O2 max) zone should reproduce the
    # regime-adjusted pace exactly, scaled to each display distance.
    perf = Performance(distance_km=5.0, time_min=20.0)
    adjusted = adjusted_pace_per_km(perf)
    paces = training_paces(perf)
    for label, km in DISPLAY_DISTANCES_KM.items():
        assert paces["V.O2 max"][label] == pytest.approx(adjusted * km)


def test_training_paces_faster_zones_are_faster():
    # Higher zone percentage => faster (lower) pace per km, monotonically.
    perf = Performance(distance_km=5.0, time_min=20.0)
    paces = training_paces(perf)
    ordered_zones = sorted(TRAINING_ZONES.items(), key=lambda kv: kv[1])
    times = [paces[label]["1000m"] for label, _ in ordered_zones]
    assert times == sorted(times, reverse=True)


@pytest.mark.parametrize(
    "minutes,expected",
    [
        (4.0, "4:00.00"),
        (65.5, "1:05:30.00"),
        (0.5, "0:30.00"),
    ],
)
def test_format_minutes(minutes, expected):
    assert format_minutes(minutes) == expected
