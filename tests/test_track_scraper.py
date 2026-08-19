"""Tests for pacechart.track_scraper's pure `parse_track_meet_results`,
against the saved HTML fixture in tests/fixtures/ (see its header comment
for provenance). No network access -- `fetch_*` wrappers are not covered
here, matching test_scraper.py's convention.
"""

from datetime import date
from pathlib import Path

import pytest

from pacechart.models import Meet
from pacechart.track_scraper import parse_track_meet_results

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def make_meet() -> Meet:
    return Meet(name="Battle for 55 Dual", date=date(2026, 3, 5), location="Panther Creek HS. Cary NC")


def test_parses_the_1600m_run():
    meet = make_meet()
    results = dict(parse_track_meet_results(load("track_meet_results.html"), meet))

    severson = results[12655]
    assert severson.distance_km == pytest.approx(1.6)
    assert severson.time_seconds == pytest.approx(5 * 60 + 3.79)
    assert severson.place == 1
    assert severson.meet == meet


def test_parses_the_3200m_run_despite_decorative_icon_markup_in_the_time_cell():
    # The 3200m row's time cell has a <small><i class="fa fa-star..."></i>
    # </small> icon ahead of the time (championship-meet quirk noted in
    # Track-Mode-Plan.md) -- get_text(strip=True) must still yield a clean
    # time string.
    meet = make_meet()
    results = dict(parse_track_meet_results(load("track_meet_results.html"), meet))

    vo = results[12774]
    assert vo.distance_km == pytest.approx(3.2)
    assert vo.time_seconds == pytest.approx(9 * 60 + 46.98)
    assert vo.place == 12


def test_excludes_running_events_under_1600m():
    meet = make_meet()
    results = dict(parse_track_meet_results(load("track_meet_results.html"), meet))
    assert 12600 not in results  # 800m Run


def test_excludes_field_events():
    meet = make_meet()
    results = dict(parse_track_meet_results(load("track_meet_results.html"), meet))
    assert 12500 not in results  # Long Jump


def test_excludes_relay_entries_including_the_team_entry_id():
    meet = make_meet()
    results = dict(parse_track_meet_results(load("track_meet_results.html"), meet))
    assert 12970 not in results  # 4x200m Relay team entry
    assert 12819 not in results  # relay leg runner


def test_excludes_a_relay_even_when_its_distance_would_otherwise_pass_the_1600m_filter():
    # The misdetection risk Track-Mode-Plan.md flags: "4x1600m Relay"'s
    # heading contains "1600m", which would pass a naive distance-only
    # filter. The relay-name exclusion must be checked first.
    meet = make_meet()
    results = dict(parse_track_meet_results(load("track_meet_results.html"), meet))
    assert 12980 not in results


def test_excludes_steeplechase_even_when_its_distance_would_otherwise_pass_the_filter():
    meet = make_meet()
    results = dict(parse_track_meet_results(load("track_meet_results.html"), meet))
    assert 12999 not in results


def test_returns_only_the_two_expected_individual_results():
    meet = make_meet()
    results = parse_track_meet_results(load("track_meet_results.html"), meet)
    athlete_ids = [athlete_id for athlete_id, _ in results]
    assert sorted(athlete_ids) == [12655, 12774]
