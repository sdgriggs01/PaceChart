"""Tests for pacechart.scraper's pure `parse_*` functions, against saved
HTML fixtures in tests/fixtures/ (captured from the live site). No
network access — `fetch_*` wrappers are intentionally not covered here.
"""

from datetime import date
from pathlib import Path

import pytest

from pacechart.models import Gender, Meet
from pacechart.scraper import parse_meet_results, parse_roster, parse_schedule

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- parse_roster --------------------------------------------------------


def test_parse_roster_finds_a_known_boys_senior():
    athletes = parse_roster(load("roster.html"))
    beck = athletes[12629]
    assert beck.name == "Beck, Ethan"
    assert beck.gender is Gender.BOYS
    assert beck.grad_year == 2027


def test_parse_roster_finds_a_known_girls_senior():
    athletes = parse_roster(load("roster.html"))
    blake = athletes[12615]
    assert blake.name == "Blake, Riley"
    assert blake.gender is Gender.GIRLS
    assert blake.grad_year == 2027


def test_parse_roster_finds_every_athlete_link():
    athletes = parse_roster(load("roster.html"))
    assert len(athletes) == 93


def test_parse_roster_athletes_start_with_no_results():
    athletes = parse_roster(load("roster.html"))
    assert all(a.results == [] for a in athletes.values())


# --- parse_schedule --------------------------------------------------------


def test_parse_schedule_finds_kickoff_classic_with_both_result_links():
    scheduled_meets = parse_schedule(load("schedule.html"))
    kickoff = next(sm for sm in scheduled_meets if sm.meet.name == "Kickoff Classic (3K)")
    assert kickoff.meet.date == date(2026, 8, 8)
    assert kickoff.meet.location == "Wake Med Park"
    assert kickoff.boys_results_url == "https://xc.greenhopetrackxc.com/index.php/meet/view/1300/M"
    assert kickoff.girls_results_url == "https://xc.greenhopetrackxc.com/index.php/meet/view/1300/F"


def test_parse_schedule_meet_without_results_has_none_links():
    scheduled_meets = parse_schedule(load("schedule.html"))
    dual_meet = next(
        sm for sm in scheduled_meets if sm.meet.name.startswith("6-way 3K")
    )
    assert dual_meet.boys_results_url is None
    assert dual_meet.girls_results_url is None


def test_parse_schedule_returns_every_meet_row():
    scheduled_meets = parse_schedule(load("schedule.html"))
    assert len(scheduled_meets) == 19


# --- parse_meet_results ------------------------------------------------------


def test_parse_meet_results_boys_3k_first_heat():
    meet = Meet(name="Kickoff Classic (3K)", date=date(2026, 8, 8), location="Wake Med Park")
    results = dict(parse_meet_results(load("meet_results_boys.html"), meet))

    ji = results[12794]
    assert ji.distance_km == pytest.approx(3.0)
    assert ji.time_seconds == pytest.approx(11 * 60 + 11.50)
    assert ji.place == 66
    assert ji.meet == meet


def test_parse_meet_results_boys_3k_second_heat_also_parsed():
    # The boys fixture has two heats ("3K Run - 11/12" and "3K Run - 9/10");
    # both should be picked up, not just the first.
    meet = Meet(name="Kickoff Classic (3K)", date=date(2026, 8, 8), location="Wake Med Park")
    results = dict(parse_meet_results(load("meet_results_boys.html"), meet))

    marbell = results[12911]
    assert marbell.distance_km == pytest.approx(3.0)
    assert marbell.time_seconds == pytest.approx(10 * 60 + 47.70)
    assert marbell.place == 28


def test_parse_meet_results_girls_5k():
    meet = Meet(name="Early Bird Classic", date=date(2026, 8, 15), location="Wake Med Park")
    results = dict(parse_meet_results(load("meet_results_girls_5k.html"), meet))

    reeves = results[13017]
    assert reeves.distance_km == pytest.approx(5.0)
    assert reeves.time_seconds == pytest.approx(18 * 60 + 53.80)
    assert reeves.place == 2


def test_parse_meet_results_returns_one_entry_per_runner():
    meet = Meet(name="Early Bird Classic", date=date(2026, 8, 15), location="Wake Med Park")
    results = parse_meet_results(load("meet_results_girls_5k.html"), meet)
    athlete_ids = [athlete_id for athlete_id, _ in results]
    assert len(athlete_ids) == len(set(athlete_ids))
    assert len(results) > 0
