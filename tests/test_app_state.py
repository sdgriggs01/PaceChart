"""Unit tests for pacechart.app_state.AppState — no Tkinter involved."""

from datetime import date

import pytest

from pacechart.app_state import AppState, GroupBy, Mode, SortBy, all_pace_keys, track_distance_label
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


def test_sorted_athletes_for_output_defaults_to_name():
    _, zed = make_athlete(1, "Zed", Gender.BOYS)
    _, amy = make_athlete(2, "Amy", Gender.BOYS)
    state = AppState(athletes={1: zed, 2: amy})

    ordered = state.sorted_athletes_for_output(Gender.BOYS)

    assert [a.name for _, a in ordered] == ["Amy", "Zed"]


def test_sorted_athletes_for_output_by_average_time_orders_fastest_first():
    fast_result = RaceResult(meet=make_meet(), distance_km=5.0, time_seconds=1000, selected=True)
    slow_result = RaceResult(meet=make_meet(), distance_km=5.0, time_seconds=1300, selected=True)
    _, slow = make_athlete(1, "Slow Sam", Gender.BOYS, results=[slow_result])
    _, fast = make_athlete(2, "Fast Fran", Gender.BOYS, results=[fast_result])
    state = AppState(athletes={1: slow, 2: fast})
    state.sort_by = SortBy.AVERAGE_TIME
    state.calculate()

    ordered = state.sorted_athletes_for_output(Gender.BOYS)

    assert [a.name for _, a in ordered] == ["Fast Fran", "Slow Sam"]


def test_sorted_athletes_for_output_by_average_time_puts_no_result_athletes_last():
    result = RaceResult(meet=make_meet(), distance_km=5.0, time_seconds=1200, selected=True)
    _, has_result = make_athlete(1, "Amy", Gender.BOYS, results=[result])
    _, no_result = make_athlete(2, "Zed", Gender.BOYS, results=[])
    state = AppState(athletes={1: has_result, 2: no_result})
    state.sort_by = SortBy.AVERAGE_TIME
    state.calculate()

    ordered = state.sorted_athletes_for_output(Gender.BOYS)

    assert [a.name for _, a in ordered] == ["Amy", "Zed"]


def test_sorted_athletes_for_output_by_average_time_before_calculate_falls_back_to_name():
    _, zed = make_athlete(1, "Zed", Gender.BOYS)
    _, amy = make_athlete(2, "Amy", Gender.BOYS)
    state = AppState(athletes={1: zed, 2: amy})
    state.sort_by = SortBy.AVERAGE_TIME

    ordered = state.sorted_athletes_for_output(Gender.BOYS)

    assert [a.name for _, a in ordered] == ["Amy", "Zed"]


def test_sorted_enabled_paces_defaults_to_grouped_by_zone():
    state = AppState()
    state.disable_all_paces()
    state.set_pace_enabled("Threshold", "Mile", True)
    state.set_pace_enabled("Easy", "1000m", True)
    state.set_pace_enabled("Easy", "Mile", True)

    ordered = state.sorted_enabled_paces()

    # Easy (lower intensity) sorts before Threshold; within a zone, Mile
    # (first in DISPLAY_DISTANCES_KM) sorts before 1000m.
    assert ordered == [("Easy", "Mile"), ("Easy", "1000m"), ("Threshold", "Mile")]


def test_mode_defaults_to_xc():
    assert AppState().mode is Mode.XC


def test_calculate_uses_3k_equivalent_in_track_mode():
    from pacechart.models import average_3k_equivalent

    result = RaceResult(meet=make_meet(), distance_km=1.6, time_seconds=300, selected=True)
    _, athlete = make_athlete(1, "Jane", Gender.GIRLS, results=[result])
    state = AppState(mode=Mode.TRACK, athletes={1: athlete})

    state.calculate()

    expected = average_3k_equivalent(athlete)
    performance = state.computed_performance[1]
    assert performance is not None
    assert performance.distance_km == pytest.approx(3.0)
    assert performance.time_min == pytest.approx(expected.time_min)


def test_calculate_still_uses_5k_equivalent_in_xc_mode():
    result = RaceResult(meet=make_meet(), distance_km=5.0, time_seconds=1200, selected=True)
    _, athlete = make_athlete(1, "Jane", Gender.GIRLS, results=[result])
    state = AppState(athletes={1: athlete})

    state.calculate()

    assert state.computed_performance[1].distance_km == pytest.approx(5.0)


def test_track_distance_label_formats_meters():
    assert track_distance_label(1.6) == "1600m"
    assert track_distance_label(3.2) == "3200m"


def test_track_grid_rows_splits_an_athlete_with_two_distances_into_two_rows():
    meet_a = make_meet("Dual", 1)
    meet_b = make_meet("Invitational", 2)
    r_1600 = RaceResult(meet=meet_a, distance_km=1.6, time_seconds=300)
    r_3200 = RaceResult(meet=meet_b, distance_km=3.2, time_seconds=620)
    _, athlete = make_athlete(1, "Jane", Gender.GIRLS, results=[r_1600, r_3200])
    state = AppState(mode=Mode.TRACK, athletes={1: athlete})

    rows = state.track_grid_rows(Gender.GIRLS)

    assert rows == [(athlete, 1.6, [r_1600]), (athlete, 3.2, [r_3200])]


def test_track_grid_rows_groups_same_distance_results_from_different_meets_into_one_row():
    meet_a = make_meet("Dual", 1)
    meet_b = make_meet("Invitational", 2)
    r1 = RaceResult(meet=meet_a, distance_km=1.6, time_seconds=305)
    r2 = RaceResult(meet=meet_b, distance_km=1.6, time_seconds=300)
    _, athlete = make_athlete(1, "Jane", Gender.GIRLS, results=[r1, r2])
    state = AppState(mode=Mode.TRACK, athletes={1: athlete})

    rows = state.track_grid_rows(Gender.GIRLS)

    assert rows == [(athlete, 1.6, [r1, r2])]


def test_track_grid_rows_skips_athletes_with_no_results():
    _, athlete = make_athlete(1, "Jane", Gender.GIRLS, results=[])
    state = AppState(mode=Mode.TRACK, athletes={1: athlete})

    assert state.track_grid_rows(Gender.GIRLS) == []


def test_sorted_enabled_paces_grouped_by_distance():
    state = AppState()
    state.disable_all_paces()
    state.set_pace_enabled("Threshold", "Mile", True)
    state.set_pace_enabled("Easy", "1000m", True)
    state.set_pace_enabled("Easy", "Mile", True)
    state.group_by = GroupBy.DISTANCE

    ordered = state.sorted_enabled_paces()

    # Mile (first in DISPLAY_DISTANCES_KM) sorts before 1000m; within a
    # distance, Easy (lower intensity) sorts before Threshold.
    assert ordered == [("Easy", "Mile"), ("Threshold", "Mile"), ("Easy", "1000m")]
