"""Pure application state for the GUI: no Tkinter dependency, so this is
unit-testable without a display. `gui.py` wires Tkinter widgets to an
instance of `AppState`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pacechart.calculator import DISPLAY_DISTANCES_KM, Performance, TRAINING_ZONES, training_paces
from pacechart.models import Athlete, Gender, RaceResult, average_3k_equivalent, average_5k_equivalent
from pacechart.scraper import ScheduledMeet

PaceKey = tuple[str, str]  # (zone label, display distance label)


def all_pace_keys() -> set[PaceKey]:
    return {(zone, dist) for zone in TRAINING_ZONES for dist in DISPLAY_DISTANCES_KM}


class GroupBy(Enum):
    """How the Output tab and PDF order their pace columns."""

    ZONE = "zone"
    DISTANCE = "distance"


class SortBy(Enum):
    """How the Output tab and PDF order their athlete rows."""

    NAME = "name"
    AVERAGE_TIME = "average_time"


class Mode(Enum):
    """Which season's data is loaded: cross-country (5000m-equivalent,
    scraped from xc.greenhopetrackxc.com) or track (3000m-equivalent,
    scraped from track.greenhopetrackxc.com). See Track-Mode-Plan.md.
    Fully separate data sets -- switching modes replaces whatever was
    loaded, never merges the two."""

    XC = "xc"
    TRACK = "track"


_AVERAGER_BY_MODE = {
    Mode.XC: average_5k_equivalent,
    Mode.TRACK: average_3k_equivalent,
}


@dataclass
class AppState:
    # Which season's data this state holds -- determines which scraper
    # module `athletes`/`scheduled_meets` were loaded from and which
    # reference distance calculate() averages to (see Mode).
    mode: Mode = Mode.XC

    athletes: dict[int, Athlete] = field(default_factory=dict)
    scheduled_meets: list[ScheduledMeet] = field(default_factory=list)

    # Which (zone, distance) combinations are enabled for the PDF/output.
    # Defaults to everything enabled (Design.md: "the full set available...
    # the user enables/disables individual ... combinations").
    enabled_paces: set[PaceKey] = field(default_factory=all_pace_keys)

    # Column ordering for the Output tab and PDF: group primarily by zone
    # (all distances for "Easy" together, etc.) or primarily by distance
    # (all zones for "Mile" together, etc.).
    group_by: GroupBy = GroupBy.ZONE

    # Row ordering for the Output tab and PDF: alphabetically by name, or
    # by the averaged 5k-equivalent time that calculate() fed into
    # training_paces() (fastest first).
    sort_by: SortBy = SortBy.NAME

    # Whether the Output tab and PDF show an extra column with each
    # athlete's averaged 5k-equivalent time (the input calculate() fed into
    # training_paces()), alongside the derived training paces.
    show_average_time_column: bool = False

    # Populated by calculate(). None means "no selected results".
    computed_performance: dict[int, Performance | None] = field(default_factory=dict)
    computed_paces: dict[int, dict[PaceKey, float] | None] = field(default_factory=dict)

    def athletes_by_gender(self, gender: Gender) -> list[Athlete]:
        return sorted(
            (a for a in self.athletes.values() if a.gender is gender),
            key=lambda a: a.name,
        )

    def meets_with_results_for(self, gender: Gender) -> list[ScheduledMeet]:
        """Meets where at least one athlete of this gender has an actual
        attached result, in schedule order. A posted results link isn't
        enough by itself (e.g. the linked page might list zero results
        for our team) — this hides meets with nothing to check off."""
        meets_with_data = {
            result.meet
            for athlete in self.athletes.values()
            if athlete.gender is gender
            for result in athlete.results
        }
        return [sm for sm in self.scheduled_meets if sm.meet in meets_with_data]

    def select_most_recent_all(self) -> None:
        """The workflow's "quick action button": select each athlete's
        single most recent result, deselecting everything else."""
        for athlete in self.athletes.values():
            athlete.select_most_recent()

    def enable_all_paces(self) -> None:
        self.enabled_paces = all_pace_keys()

    def disable_all_paces(self) -> None:
        self.enabled_paces = set()

    def toggle_paces_for_distance(self, distance: str) -> None:
        """Paces-tab column header click: if every zone at this distance is
        already enabled, clear them all; otherwise enable every zone at
        this distance."""
        keys = {(zone, distance) for zone in TRAINING_ZONES}
        if keys <= self.enabled_paces:
            self.enabled_paces -= keys
        else:
            self.enabled_paces |= keys

    def toggle_paces_for_zone(self, zone: str) -> None:
        """Paces-tab row header click: if every distance at this zone is
        already enabled, clear them all; otherwise enable every distance
        at this zone."""
        keys = {(zone, distance) for distance in DISPLAY_DISTANCES_KM}
        if keys <= self.enabled_paces:
            self.enabled_paces -= keys
        else:
            self.enabled_paces |= keys

    def set_pace_enabled(self, zone: str, distance: str, enabled: bool) -> None:
        key = (zone, distance)
        if enabled:
            self.enabled_paces.add(key)
        else:
            self.enabled_paces.discard(key)

    def sorted_enabled_paces(self) -> list[PaceKey]:
        """Enabled (zone, distance) pairs in display order — the column
        order used by both the GUI's Output tab and the PDF report.
        Zones are always ordered by increasing intensity and distances
        from Mile down to 200m; `group_by` picks which is primary."""
        zone_order = list(TRAINING_ZONES)
        dist_order = list(DISPLAY_DISTANCES_KM)
        if self.group_by is GroupBy.DISTANCE:
            key = lambda k: (dist_order.index(k[1]), zone_order.index(k[0]))
        else:
            key = lambda k: (zone_order.index(k[0]), dist_order.index(k[1]))
        return sorted(self.enabled_paces, key=key)

    def sorted_athletes_for_output(self, gender: Gender) -> list[tuple[int, Athlete]]:
        """Row order for the Output tab and PDF, for one gender.

        `SortBy.NAME` orders alphabetically. `SortBy.AVERAGE_TIME` orders by
        each athlete's computed average 5k-equivalent time (the value
        `calculate()` fed into `training_paces()`), fastest first; athletes
        with no computed time (calc not yet run, or nothing selected) sort
        after everyone with a time, alphabetically among themselves.

        XC mode keeps every athlete of this gender, even with no computed
        performance (Design.md: "an athlete with no selected results still
        gets a row... blank cells rather than omitting the athlete"). Track
        mode omits athletes with no computed performance entirely -- a
        track roster includes sprinters/jumpers/throwers etc. who never run
        a 1600m+ distance event, so keeping every athlete would mean the
        output is mostly blank rows.
        """
        entries = [(aid, a) for aid, a in self.athletes.items() if a.gender is gender]
        if self.mode is Mode.TRACK:
            entries = [(aid, a) for aid, a in entries if self.computed_performance.get(aid) is not None]
        if self.sort_by is SortBy.AVERAGE_TIME:
            def key(entry: tuple[int, Athlete]) -> tuple[bool, float, str]:
                athlete_id, athlete = entry
                performance = self.computed_performance.get(athlete_id)
                return (performance is None, performance.time_min if performance else 0.0, athlete.name)

            return sorted(entries, key=key)
        return sorted(entries, key=lambda entry: entry[1].name)

    def calculate(self) -> None:
        """Design.md workflow steps 3-4: average each athlete's selected
        results into a 5k-equivalent (XC mode) or 3k-equivalent (Track
        mode) performance, then generate every enabled training pace from
        it. Athletes with no selected results get None in both dicts
        (workflow: "no results generate a row with no results, but not
        omit the athlete")."""
        self.computed_performance.clear()
        self.computed_paces.clear()
        averager = _AVERAGER_BY_MODE[self.mode]

        for athlete_id, athlete in self.athletes.items():
            performance = averager(athlete)
            self.computed_performance[athlete_id] = performance

            if performance is None:
                self.computed_paces[athlete_id] = None
                continue

            full_paces = training_paces(performance)
            self.computed_paces[athlete_id] = {
                (zone, dist): full_paces[zone][dist]
                for zone, dist in self.enabled_paces
            }

    def track_grid_rows(self, gender: Gender) -> list[tuple[Athlete, float, list[RaceResult]]]:
        """Track-Mode-Plan.md's results-grid decision: one display row per
        (athlete, event distance) rather than one row per athlete, since a
        track athlete can have both a 1600m and a 3200m result in the same
        season (even at the same meet) and each needs its own checkboxes.
        Purely a display grouping over `athlete.results` -- `Athlete`/
        `RaceResult` themselves are unchanged, and `calculate()` still
        averages every selected result together regardless of which row it
        was checked from.

        Returns one `(athlete, distance_km, results)` tuple per athlete per
        distinct distance among their results, athletes sorted by name then
        distance ascending. An athlete with no track results (e.g. ran only
        sprints/field events, all filtered out by the scraper) contributes
        no rows."""
        rows: list[tuple[Athlete, float, list[RaceResult]]] = []
        for athlete in self.athletes_by_gender(gender):
            distances = sorted({result.distance_km for result in athlete.results})
            for distance_km in distances:
                results = [r for r in athlete.results if r.distance_km == distance_km]
                rows.append((athlete, distance_km, results))
        return rows


def track_distance_label(distance_km: float) -> str:
    """Display label for a track_grid_rows() row, e.g. 1.6 -> "1600m"."""
    return f"{round(distance_km * 1000)}m"
