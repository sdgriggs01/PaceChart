"""Unit tests for pacechart.models: construction, validation, and the
selection helpers, independent of the calculator's actual math (that's
covered in test_integration.py).
"""

from datetime import date

import pytest

from pacechart.models import Athlete, Gender, Meet, RaceResult


def make_meet(name="Meet", day=1) -> Meet:
    return Meet(name=name, date=date(2025, 9, day), location="Somewhere")


def test_meet_is_hashable_and_frozen():
    m1 = make_meet()
    m2 = make_meet()
    assert m1 == m2
    with pytest.raises(AttributeError):
        m1.name = "Other"  # type: ignore[misc]


def test_race_result_defaults_unselected():
    result = RaceResult(meet=make_meet(), distance_km=5.0, time_seconds=1200)
    assert result.selected is False
    assert result.place is None


def test_race_result_rejects_non_positive_distance():
    with pytest.raises(ValueError):
        RaceResult(meet=make_meet(), distance_km=0, time_seconds=1200)


def test_race_result_rejects_non_positive_time():
    with pytest.raises(ValueError):
        RaceResult(meet=make_meet(), distance_km=5.0, time_seconds=0)


def test_race_result_to_performance_converts_seconds_to_minutes():
    result = RaceResult(meet=make_meet(), distance_km=5.0, time_seconds=1230)
    perf = result.to_performance()
    assert perf.distance_km == pytest.approx(5.0)
    assert perf.time_min == pytest.approx(20.5)


def test_athlete_selected_results_filters_unselected():
    r1 = RaceResult(meet=make_meet("A", 1), distance_km=5.0, time_seconds=1200, selected=True)
    r2 = RaceResult(meet=make_meet("B", 2), distance_km=5.0, time_seconds=1250, selected=False)
    athlete = Athlete(name="Jane Doe", gender=Gender.GIRLS, results=[r1, r2])
    assert athlete.selected_results() == [r1]


def test_select_most_recent_picks_latest_meet_date():
    earlier = RaceResult(meet=make_meet("Early", 1), distance_km=5.0, time_seconds=1300)
    later = RaceResult(meet=make_meet("Late", 20), distance_km=5.0, time_seconds=1250)
    athlete = Athlete(name="Jane Doe", gender=Gender.GIRLS, results=[earlier, later])

    athlete.select_most_recent()

    assert athlete.selected_results() == [later]


def test_select_most_recent_deselects_previously_selected():
    earlier = RaceResult(meet=make_meet("Early", 1), distance_km=5.0, time_seconds=1300, selected=True)
    later = RaceResult(meet=make_meet("Late", 20), distance_km=5.0, time_seconds=1250)
    athlete = Athlete(name="Jane Doe", gender=Gender.GIRLS, results=[earlier, later])

    athlete.select_most_recent()

    assert earlier.selected is False
    assert later.selected is True


def test_select_most_recent_is_noop_with_no_results():
    athlete = Athlete(name="Jane Doe", gender=Gender.GIRLS, results=[])
    athlete.select_most_recent()  # should not raise
    assert athlete.selected_results() == []
