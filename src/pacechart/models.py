"""Data models for athletes, meets, and race results.

See Design.md for the workflow these support: a table of athletes x
meets with checkboxes to select results, a "select most recent" quick
action, and averaging selected results into one 5k-equivalent
performance per athlete (see `average_5k_equivalent`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from pacechart.calculator import Performance, equivalent_performances


class Gender(Enum):
    BOYS = "boys"
    GIRLS = "girls"


# Display abbreviation shared by the GUI's Output tab and the PDF report.
GENDER_LABELS = {Gender.BOYS: "M", Gender.GIRLS: "F"}


@dataclass(frozen=True)
class Meet:
    """A cross-country meet, as listed on the schedule page."""

    name: str
    date: date
    location: str | None = None


@dataclass
class RaceResult:
    """One athlete's result at one meet."""

    meet: Meet
    distance_km: float
    time_seconds: float
    place: int | None = None
    selected: bool = False

    def __post_init__(self) -> None:
        if self.distance_km <= 0:
            raise ValueError("distance_km must be positive")
        if self.time_seconds <= 0:
            raise ValueError("time_seconds must be positive")

    def to_performance(self) -> Performance:
        return Performance(distance_km=self.distance_km, time_min=self.time_seconds / 60.0)


@dataclass
class Athlete:
    """An athlete on the roster, with zero or more race results."""

    name: str
    gender: Gender
    grad_year: int | None = None
    results: list[RaceResult] = field(default_factory=list)

    def select_most_recent(self) -> None:
        """Deselect all results, then select only the most recent by meet date.

        This is the "quick action button" from Design.md's workflow step 1.
        No-op if the athlete has no results.
        """
        if not self.results:
            return
        latest = max(self.results, key=lambda r: r.meet.date)
        for result in self.results:
            result.selected = result is latest

    def selected_results(self) -> list[RaceResult]:
        return [r for r in self.results if r.selected]


def to_5k_equivalent_minutes(result: RaceResult) -> float:
    """Convert one race result to a 5000m-equivalent time, in minutes.

    Runs the result's own distance through the full calculator model
    (regime selection -> Q -> equivalent-performance table) rather than
    special-casing 3k/5k, so any distance the scraper produces is
    handled the same way.
    """
    predicted = equivalent_performances(result.to_performance())
    return predicted["5000m"]


def average_5k_equivalent(athlete: Athlete) -> Performance | None:
    """Section/workflow step 3 of Design.md: average an athlete's selected
    results, each converted to a 5000m-equivalent time first.

    Returns None if the athlete has no selected results.
    """
    selected = athlete.selected_results()
    if not selected:
        return None
    converted_times = [to_5k_equivalent_minutes(r) for r in selected]
    avg_time_min = sum(converted_times) / len(converted_times)
    return Performance(distance_km=5.0, time_min=avg_time_min)


def to_3k_equivalent_minutes(result: RaceResult) -> float:
    """Track mode's analogue of `to_5k_equivalent_minutes`: converts one
    race result to a 3000m-equivalent time, in minutes (Track-Mode-Plan.md's
    "Calculator reuse" -- 3000m is already the model's internal reference
    distance, so this is just a different key off the same table)."""
    predicted = equivalent_performances(result.to_performance())
    return predicted["3000m"]


def average_3k_equivalent(athlete: Athlete) -> Performance | None:
    """Track mode's analogue of `average_5k_equivalent`: average an
    athlete's selected results (each a 1600m+ track distance event, per
    Track-Mode-Plan.md decision 1), each converted to a 3000m-equivalent
    time first.

    Returns None if the athlete has no selected results.
    """
    selected = athlete.selected_results()
    if not selected:
        return None
    converted_times = [to_3k_equivalent_minutes(r) for r in selected]
    avg_time_min = sum(converted_times) / len(converted_times)
    return Performance(distance_km=3.0, time_min=avg_time_min)
