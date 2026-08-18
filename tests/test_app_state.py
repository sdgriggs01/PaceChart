"""Unit tests for pacechart.app_state.AppState — no Tkinter involved."""

from datetime import date

import pytest

from pacechart.app_state import AppState, all_pace_keys
from pacechart.calculator import DISPLAY_DISTANCES_KM, TRAINING_ZONES
from pacechart.models import Athlete, Gender, Meet, RaceResult
from pacechart.scraper import ScheduledMeet


def make_meet(name="Meet", day=1) -> Meet:
    return Meet(name=name, date=date(2025, 9, day), location="Somewhere")


def make_athlete(athlete_id, name, gender, results=None) -> tuple[int, Athlete]:
    return athlete_id, Athlete(name=name, gender=gender, results=results or [])


def test_enabled_paces_defaults_to_everything():
    state = AppState()
    assert state.enabled_paces == all_pace_keys()
    assert len(state.enabled_paces) == 11 * 9


def test_athletes_by_gender_filters_and_sorts():
    state = AppState()
    _, a = make_athlete(1, "Zed", Gender.BOYS)
    _, b = make_athlete(2, "Amy", Gender.BOYS)
    _, c = make_athlete(3, "Sue", Gender.GIRLS)
    state.athletes = {1: a, 2: b, 3: c}

    boys = state.athletes_by_gender(Gender.BOYS)
    assert [ath.name for ath in boys] == ["Amy", "Zed"]
    assert state.athletes_by_gender(Gender.GIRLS) == [c]


def test_meets_with_results_for_requires_an_actual_attached_result():
    meet_a = make_meet("A", 1)
    meet_b = make_meet("B", 2)
    meet_c = make_meet("C", 3)
    meet_d = make_meet("D", 4)
    sm_a = ScheduledMeet(meet=meet_a, boys_results_url="b", girls_results_url="g")
    sm_b = ScheduledMeet(meet=meet_b, boys_results_url="b", girls_results_url=None)
    sm_c = ScheduledMeet(meet=meet_c, boys_results_url=None, girls_results_url=None)
    # Has a posted link, but nobody actually has a result for it (e.g. the
    # linked page listed zero results for our team) — should still be hidden.
    sm_d = ScheduledMeet(meet=meet_d, boys_results_url="b", girls_results_url="g")

    _, boy = make_athlete(
        1,
        "Bob",
        Gender.BOYS,
        results=[
            RaceResult(meet=meet_a, distance_km=5.0, time_seconds=1200),
            RaceResult(meet=meet_b, distance_km=5.0, time_seconds=1210),
        ],
    )
    _, girl = make_athlete(
        2,
        "Gina",
        Gender.GIRLS,
        results=[RaceResult(meet=meet_a, distance_km=5.0, time_seconds=1300)],
    )
    state = AppState(athletes={1: boy, 2: girl}, scheduled_meets=[sm_a, sm_b, sm_c, sm_d])

    assert state.meets_with_results_for(Gender.BOYS) == [sm_a, sm_b]
    assert state.meets_with_results_for(Gender.GIRLS) == [sm_a]


def test_select_most_recent_all_applies_to_every_athlete():
    early = RaceResult(meet=make_meet("Early", 1), distance_km=5.0, time_seconds=1300)
    late = RaceResult(meet=make_meet("Late", 20), distance_km=5.0, time_seconds=1250)
    _, athlete = make_athlete(1, "Jane", Gender.GIRLS, results=[early, late])
    state = AppState(athletes={1: athlete})

    state.select_most_recent_all()

    assert early.selected is False
    assert late.selected is True


def test_enable_disable_all_paces():
    state = AppState()
    state.disable_all_paces()
    assert state.enabled_paces == set()
    state.enable_all_paces()
    assert state.enabled_paces == all_pace_keys()


def test_set_pace_enabled_toggles_single_combination():
    state = AppState()
    state.set_pace_enabled("Threshold", "1000m", False)
    assert ("Threshold", "1000m") not in state.enabled_paces

    state.set_pace_enabled("Threshold", "1000m", True)
    assert ("Threshold", "1000m") in state.enabled_paces


def test_toggle_paces_for_distance_enables_every_zone_at_that_distance_when_not_full():
    state = AppState()
    state.disable_all_paces()

    state.toggle_paces_for_distance("1000m")

    assert state.enabled_paces == {(zone, "1000m") for zone in TRAINING_ZONES}


def test_toggle_paces_for_distance_only_adds_does_not_remove_others():
    state = AppState()
    state.disable_all_paces()
    state.set_pace_enabled("Easy", "Mile", True)

    state.toggle_paces_for_distance("1000m")

    assert ("Easy", "Mile") in state.enabled_paces
    assert {(zone, "1000m") for zone in TRAINING_ZONES} <= state.enabled_paces


def test_toggle_paces_for_distance_clears_when_column_fully_selected():
    state = AppState()
    state.disable_all_paces()
    state.set_pace_enabled("Easy", "Mile", True)  # unrelated selection, should survive
    state.toggle_paces_for_distance("1000m")  # fully selects the 1000m column

    state.toggle_paces_for_distance("1000m")  # click again -> should clear it

    assert not any(dist == "1000m" for _, dist in state.enabled_paces)
    assert ("Easy", "Mile") in state.enabled_paces


def test_toggle_paces_for_zone_enables_every_distance_at_that_zone_when_not_full():
    state = AppState()
    state.disable_all_paces()

    state.toggle_paces_for_zone("Threshold")

    assert state.enabled_paces == {("Threshold", dist) for dist in DISPLAY_DISTANCES_KM}


def test_toggle_paces_for_zone_only_adds_does_not_remove_others():
    state = AppState()
    state.disable_all_paces()
    state.set_pace_enabled("Easy", "Mile", True)

    state.toggle_paces_for_zone("Threshold")

    assert ("Easy", "Mile") in state.enabled_paces
    assert {("Threshold", dist) for dist in DISPLAY_DISTANCES_KM} <= state.enabled_paces


def test_toggle_paces_for_zone_clears_when_row_fully_selected():
    state = AppState()
    state.disable_all_paces()
    state.set_pace_enabled("Easy", "Mile", True)  # unrelated selection, should survive
    state.toggle_paces_for_zone("Threshold")  # fully selects the Threshold row

    state.toggle_paces_for_zone("Threshold")  # click again -> should clear it

    assert not any(zone == "Threshold" for zone, _ in state.enabled_paces)
    assert ("Easy", "Mile") in state.enabled_paces


def test_calculate_gives_none_for_athlete_with_no_selected_results():
    _, athlete = make_athlete(1, "Jane", Gender.GIRLS, results=[])
    state = AppState(athletes={1: athlete})

    state.calculate()

    assert state.computed_performance[1] is None
    assert state.computed_paces[1] is None


def test_calculate_populates_only_enabled_pace_keys():
    result = RaceResult(meet=make_meet(), distance_km=5.0, time_seconds=1200, selected=True)
    _, athlete = make_athlete(1, "Jane", Gender.GIRLS, results=[result])
    state = AppState(athletes={1: athlete})
    state.disable_all_paces()
    state.set_pace_enabled("V.O2 max", "1000m", True)
    state.set_pace_enabled("Easy", "Mile", True)

    state.calculate()

    assert state.computed_performance[1] is not None
    assert set(state.computed_paces[1].keys()) == {("V.O2 max", "1000m"), ("Easy", "Mile")}


def test_calculate_clears_previous_results_first():
    result = RaceResult(meet=make_meet(), distance_km=5.0, time_seconds=1200, selected=True)
    _, athlete = make_athlete(1, "Jane", Gender.GIRLS, results=[result])
    state = AppState(athletes={1: athlete})
    state.calculate()
    assert state.computed_performance[1] is not None

    result.selected = False
    state.calculate()

    assert state.computed_performance[1] is None
    assert state.computed_paces[1] is None
