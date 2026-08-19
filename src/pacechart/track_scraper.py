"""Scraper for the Green Hope Track website.

`track.greenhopetrackxc.com` shares its roster/schedule page structure
with `xc.greenhopetrackxc.com` (see `scraper.py`), so `parse_roster`/
`parse_schedule` are reused as-is, just pointed at different URLs via
`fetch_roster`/`fetch_schedule`'s `url` parameter. Meet-results pages use
a different template, so this module has its own parser for those. Page
structure this was written against (see Track-Mode-Plan.md for the full
research, including verbatim HTML examples):

- Meet results (one page per meet+gender): one plain `<h4>` per event
  (e.g. "1600m Run", "3200m Run", "4x800m Relay" -- metric
  "{distance}m {Dash|Run|Hurdles}" naming, no "K" notation), immediately
  followed by its results `<table>` -- there is no `<thead>`/`<th>`
  anywhere on the page, unlike the XC template. Each results row has 3
  columns: Place, Time, Runner (vs. XC's 4-column Pos/Pts/Time/Runner).
  Relay "Runner" cells link a synthetic team-entry athlete id first, not
  an individual -- relay (and steeplechase) headings are excluded
  outright by name, regardless of what distance their text would
  otherwise parse to.
"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from pacechart.models import Athlete, Gender, Meet, RaceResult
from pacechart.scraper import (
    _ATHLETE_HREF_RE,
    REQUEST_TIMEOUT_SECONDS,
    ScheduledMeet,
    _athlete_id_from_href,
    _parse_time_to_seconds,
    _session_with_headers,
    fetch_roster,
    fetch_schedule,
)

TRACK_ROSTER_URL = "https://track.greenhopetrackxc.com/index.php/athletes/roster"
TRACK_SCHEDULE_URL = "https://track.greenhopetrackxc.com/index.php/schedule/view"

# Track-Mode-Plan.md decision 1: only 1600m/mile-and-longer running
# events feed the 3000m-equivalent conversion.
MIN_TRACK_DISTANCE_KM = 1.6

# Anchored + requires "Run" so sprints ("100m Dash") and hurdles
# ("110m Hurdles") never match at all, not just fail the distance check.
_TRACK_DISTANCE_RE = re.compile(r"^(\d+)\s*m\s+Run\b", re.IGNORECASE)

# Checked before distance extraction: a relay's "Runner" cell links a
# team-entry id, not an individual athlete, so a heading like
# "4x1600m Relay" must never be treated as an individual 1600m result.
# Steeplechase is excluded defensively too (never observed on the site,
# but its times aren't comparable to flat-race paces).
_EXCLUDED_HEADING_RE = re.compile(r"relay|steeplechase", re.IGNORECASE)


def fetch_track_roster(session: requests.Session | None = None) -> dict[int, Athlete]:
    return fetch_roster(session=session, url=TRACK_ROSTER_URL)


def fetch_track_schedule(session: requests.Session | None = None) -> list[ScheduledMeet]:
    return fetch_schedule(session=session, url=TRACK_SCHEDULE_URL)


def _find_track_results_table(heading: Tag) -> Tag | None:
    """The track template has no `<thead>`/`<th>` to search by (unlike
    XC's `_find_results_table`) -- each event `<h4>` is immediately
    followed by exactly one results `<table>` before the next heading."""
    return heading.find_next("table")


def parse_track_meet_results(html: str, meet: Meet) -> list[tuple[int, RaceResult]]:
    """Returns (athlete_id, RaceResult) pairs for every 1600m+ running heat
    on the page. Field events, sub-1600m running events, relays, and
    steeplechase are all skipped -- see module docstring and
    Track-Mode-Plan.md's "Distance detection / filtering logic"."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[tuple[int, RaceResult]] = []

    for heading in soup.find_all("h4"):
        heading_text = heading.get_text(strip=True)
        if _EXCLUDED_HEADING_RE.search(heading_text):
            continue

        distance_match = _TRACK_DISTANCE_RE.match(heading_text)
        if not distance_match:
            continue
        distance_km = int(distance_match.group(1)) / 1000.0
        if distance_km < MIN_TRACK_DISTANCE_KM:
            continue

        results_table = _find_track_results_table(heading)
        if results_table is None:
            continue

        for row in results_table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            pos_text = cells[0].get_text(strip=True)
            place = int(pos_text) if pos_text.isdigit() else None

            time_text = cells[1].get_text(strip=True)
            try:
                time_seconds = _parse_time_to_seconds(time_text)
            except ValueError:
                continue

            link = cells[2].find("a", href=_ATHLETE_HREF_RE)
            if link is None:
                continue
            athlete_id = _athlete_id_from_href(link["href"])

            result = RaceResult(meet=meet, distance_km=distance_km, time_seconds=time_seconds, place=place)
            results.append((athlete_id, result))

    return results


def fetch_track_meet_results(
    scheduled: ScheduledMeet, gender: Gender, session: requests.Session | None = None
) -> list[tuple[int, RaceResult]]:
    url = scheduled.results_url(gender)
    if url is None:
        return []
    session = _session_with_headers(session)
    response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return parse_track_meet_results(response.text, scheduled.meet)
