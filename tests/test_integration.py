"""Integration tests: models.py wired into calculator.py.

These confirm the wiring (RaceResult -> Performance -> calculator
functions -> Athlete-level averaging) is correct, reusing calculator.py
itself as the source of truth for the math (already covered by
test_calculator.py) rather than re-deriving expected numbers by hand.
"""

from datetime import date

import pytest

from pacechart.calculator import (
    DISPLAY_DISTANCES_KM,
    Performance,
    adjusted_pace_per_km,
    equivalent_performances,
    training_paces,
)
from pacechart.models import (
    Athlete,
    Gender,
    Meet,
    RaceResult,
    average_5k_equivalent,
    to_5k_equivalent_minutes,
)


def make_meet(name="Meet", day=1) -> Meet:
    return Meet(name=name, date=date(2025, 9, day), location="Somewhere")


def test_to_5k_equivalent_for_5k_result_matches_calculator_directly():
    result = RaceResult(meet=make_meet(), distance_km=5.0, time_seconds=1200)
    expected = equivalent_performances(result.to_performance())["5000m"]
    assert to_5k_equivalent_minutes(result) == pytest.approx(expected)


def test_to_5k_equivalent_for_3k_result_matches_calculator_directly():
    result = RaceResult(meet=make_meet(), distance_km=3.0, time_seconds=660)
    expected = equivalent_performances(result.to_performance())["5000m"]
    assert to_5k_equivalent_minutes(result) == pytest.approx(expected)


def test_average_5k_equivalent_returns_none_with_no_selection():
    r1 = RaceResult(meet=make_meet("A", 1), distance_km=5.0, time_seconds=1200, selected=False)
    athlete = Athlete(name="Jane Doe", gender=Gender.GIRLS, results=[r1])
    assert average_5k_equivalent(athlete) is None


def test_average_5k_equivalent_ignores_unselected_results():
    selected = RaceResult(meet=make_meet("A", 1), distance_km=5.0, time_seconds=1200, selected=True)
    unselected = RaceResult(meet=make_meet("B", 2), distance_km=5.0, time_seconds=99999, selected=False)
    athlete = Athlete(name="Jane Doe", gender=Gender.GIRLS, results=[selected, unselected])

    performance = average_5k_equivalent(athlete)

    expected = equivalent_performances(selected.to_performance())["5000m"]
    assert performance is not None
    assert performance.distance_km == pytest.approx(5.0)
    assert performance.time_min == pytest.approx(expected)


def test_average_5k_equivalent_averages_converted_times_of_mixed_distances():
    r_3k = RaceResult(meet=make_meet("3k race", 1), distance_km=3.0, time_seconds=660, selected=True)
    r_5k = RaceResult(meet=make_meet("5k race", 2), distance_km=5.0, time_seconds=1200, selected=True)
    athlete = Athlete(name="Jane Doe", gender=Gender.GIRLS, results=[r_3k, r_5k])

    performance = average_5k_equivalent(athlete)

    expected_3k = equivalent_performances(r_3k.to_performance())["5000m"]
    expected_5k = equivalent_performances(r_5k.to_performance())["5000m"]
    expected_avg = (expected_3k + expected_5k) / 2

    assert performance is not None
    assert performance.distance_km == pytest.approx(5.0)
    assert performance.time_min == pytest.approx(expected_avg)


def test_averaged_performance_feeds_training_paces_end_to_end():
    # Full chain: two selected results -> averaged 5k Performance ->
    # training_paces(). Sanity-check via the same 100%-zone round-trip
    # identity used in test_calculator.py.
    r1 = RaceResult(meet=make_meet("A", 1), distance_km=5.0, time_seconds=1180, selected=True)
    r2 = RaceResult(meet=make_meet("B", 2), distance_km=5.0, time_seconds=1220, selected=True)
    athlete = Athlete(name="Jane Doe", gender=Gender.GIRLS, results=[r1, r2])

    performance = average_5k_equivalent(athlete)
    assert performance is not None

    adjusted = adjusted_pace_per_km(performance)
    paces = training_paces(performance)
    for label, km in DISPLAY_DISTANCES_KM.items():
        assert paces["V.O2 max"][label] == pytest.approx(adjusted * km)
