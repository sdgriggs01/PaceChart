"""Scraper for the Green Hope XC website.

Split into pure `parse_*` functions (take HTML text, return data — unit
tested offline against saved fixtures) and thin `fetch_*` functions
(network I/O via requests, not covered by the automated test suite).

Page structures this was written against:
- Roster: https://xc.greenhopetrackxc.com/index.php/athletes/roster
  `<div id="boys">`/`<div id="girls">`, each with one `<div class="col-md-3">`
  per class year (`<h4 class="title-divider"><small>Class of YYYY</small></h4>`
  followed by a `<table>` of `<a href=".../athletes/view/ID">Last, First</a>`).
- Schedule: https://xc.greenhopetrackxc.com/index.php/schedule/view
  One `<table>` with columns Day, Date (MM/DD/YY), Time, Meet, Location,
  Boys results link, Girls results link (link cells are `&nbsp;` if no
  results are posted yet).
- Meet results (one page per meet+gender, linked from the schedule): one
  `<h4 class="title">` per heat (e.g. "3K Run - 11/12" or "5K Run") giving
  the distance, followed by a team-scoring table and an individual-results
  table (`<th>Runner</th>` identifies it) with Pos/Pts/Time/Runner columns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from pacechart.models import Athlete, Gender, Meet, RaceResult

ROSTER_URL = "https://xc.greenhopetrackxc.com/index.php/athletes/roster"
SCHEDULE_URL = "https://xc.greenhopetrackxc.com/index.php/schedule/view"

REQUEST_TIMEOUT_SECONDS = 30

# The site rejects requests without a browser-like User-Agent (406 Not
# Acceptable with the default `requests` UA).
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def _session_with_headers(session: requests.Session | None) -> requests.Session:
    session = session or requests.Session()
    session.headers["User-Agent"] = DEFAULT_HEADERS["User-Agent"]
    return session

_ATHLETE_HREF_RE = re.compile(r"/athletes/view/(\d+)")
_GRAD_YEAR_RE = re.compile(r"Class of (\d{4})")
_DISTANCE_RE = re.compile(r"([\d.]+)\s*K", re.IGNORECASE)


@dataclass(frozen=True)
class ScheduledMeet:
    """One row of the schedule page: a meet plus its (possibly absent) results links."""

    meet: Meet
    boys_results_url: str | None
    girls_results_url: str | None

    def results_url(self, gender: Gender) -> str | None:
        return self.boys_results_url if gender is Gender.BOYS else self.girls_results_url


def _athlete_id_from_href(href: str) -> int:
    match = _ATHLETE_HREF_RE.search(href)
    if not match:
        raise ValueError(f"Could not find an athlete id in href: {href!r}")
    return int(match.group(1))


def _parse_time_to_seconds(text: str) -> float:
    parts = text.strip().split(":")
    if len(parts) == 2:
        minutes, seconds = (float(p) for p in parts)
        hours = 0.0
    elif len(parts) == 3:
        hours, minutes, seconds = (float(p) for p in parts)
    else:
        raise ValueError(f"Unrecognized time format: {text!r}")
    return hours * 3600 + minutes * 60 + seconds


# --- Roster ------------------------------------------------------------------


def parse_roster(html: str) -> dict[int, Athlete]:
    """Returns athletes keyed by their profile id (from `/athletes/view/{id}`)."""
    soup = BeautifulSoup(html, "html.parser")
    athletes: dict[int, Athlete] = {}

    for gender, pane_id in ((Gender.BOYS, "boys"), (Gender.GIRLS, "girls")):
        pane = soup.find(id=pane_id)
        if pane is None:
            continue

        for heading in pane.find_all("h4", class_="title-divider"):
            grad_year = None
            small = heading.find("small")
            if small is not None:
                match = _GRAD_YEAR_RE.search(small.get_text())
                if match:
                    grad_year = int(match.group(1))

            table = heading.find_next("table")
            if table is None:
                continue

            for row in table.select("tbody tr"):
                link = row.find("a", href=_ATHLETE_HREF_RE)
                if link is None:
                    continue
                athlete_id = _athlete_id_from_href(link["href"])
                name = link.get_text(strip=True)
                athletes[athlete_id] = Athlete(name=name, gender=gender, grad_year=grad_year)

    return athletes


def fetch_roster(session: requests.Session | None = None) -> dict[int, Athlete]:
    session = _session_with_headers(session)
    response = session.get(ROSTER_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return parse_roster(response.text)


# --- Schedule ------------------------------------------------------------------


def parse_schedule(html: str) -> list[ScheduledMeet]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return []

    scheduled_meets: list[ScheduledMeet] = []
    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 7:
            continue

        date_text = cells[1].get_text(strip=True)
        try:
            meet_date = datetime.strptime(date_text, "%m/%d/%y").date()
        except ValueError:
            continue

        name = cells[3].get_text(strip=True)
        location = cells[4].get_text(strip=True) or None

        boys_link = cells[5].find("a")
        girls_link = cells[6].find("a")

        scheduled_meets.append(
            ScheduledMeet(
                meet=Meet(name=name, date=meet_date, location=location),
                boys_results_url=boys_link["href"] if boys_link else None,
                girls_results_url=girls_link["href"] if girls_link else None,
            )
        )

    return scheduled_meets


def fetch_schedule(session: requests.Session | None = None) -> list[ScheduledMeet]:
    session = _session_with_headers(session)
    response = session.get(SCHEDULE_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return parse_schedule(response.text)


# --- Meet results ------------------------------------------------------------


def _find_results_table(heat_heading: Tag) -> Tag | None:
    container = heat_heading.find_parent("div", class_="row") or heat_heading.parent
    if container is None:
        return None
    for table in container.find_all("table"):
        thead = table.find("thead")
        if thead is not None and "Runner" in thead.get_text():
            return table
    return None


def parse_meet_results(html: str, meet: Meet) -> list[tuple[int, RaceResult]]:
    """Returns (athlete_id, RaceResult) pairs for every heat on the page."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[tuple[int, RaceResult]] = []

    for heading in soup.find_all("h4", class_="title"):
        distance_match = _DISTANCE_RE.search(heading.get_text())
        if not distance_match:
            continue
        distance_km = float(distance_match.group(1))

        results_table = _find_results_table(heading)
        if results_table is None:
            continue

        for row in results_table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            pos_text = cells[0].get_text(strip=True)
            place = int(pos_text) if pos_text.isdigit() else None

            time_text = cells[2].get_text(strip=True)
            try:
                time_seconds = _parse_time_to_seconds(time_text)
            except ValueError:
                continue

            link = cells[3].find("a", href=_ATHLETE_HREF_RE)
            if link is None:
                continue
            athlete_id = _athlete_id_from_href(link["href"])

            result = RaceResult(meet=meet, distance_km=distance_km, time_seconds=time_seconds, place=place)
            results.append((athlete_id, result))

    return results


def fetch_meet_results(
    scheduled: ScheduledMeet, gender: Gender, session: requests.Session | None = None
) -> list[tuple[int, RaceResult]]:
    url = scheduled.results_url(gender)
    if url is None:
        return []
    session = _session_with_headers(session)
    response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return parse_meet_results(response.text, scheduled.meet)


# --- Orchestration -------------------------------------------------------------


def attach_results(athletes: dict[int, Athlete], results: list[tuple[int, RaceResult]]) -> None:
    """Appends each result to its athlete's `results` list. Results for
    unknown athlete ids are silently skipped (e.g. an opposing school's
    runner appearing in a combined results table)."""
    for athlete_id, result in results:
        athlete = athletes.get(athlete_id)
        if athlete is not None:
            athlete.results.append(result)
