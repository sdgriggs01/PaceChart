"""Unit tests for pacechart.app_state.AppState — no Tkinter involved."""

from datetime import date

import pytest

from pacechart.app_state import AppState, all_pace_keys
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


def test_meets_with_results_for_filters_by_gender_link():
    state = AppState()
    has_both = ScheduledMeet(meet=make_meet("A", 1), boys_results_url="b", girls_results_url="g")
    boys_only = ScheduledMeet(meet=make_meet("B", 2), boys_results_url="b", girls_results_url=None)
    none_yet = ScheduledMeet(meet=make_meet("C", 3), boys_results_url=None, girls_results_url=None)
    state.scheduled_meets = [has_both, boys_only, none_yet]

    assert state.meets_with_results_for(Gender.BOYS) == [has_both, boys_only]
    assert state.meets_with_results_for(Gender.GIRLS) == [has_both]


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
