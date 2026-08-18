"""Pure application state for the GUI: no Tkinter dependency, so this is
unit-testable without a display. `gui.py` wires Tkinter widgets to an
instance of `AppState`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pacechart.calculator import DISPLAY_DISTANCES_KM, Performance, TRAINING_ZONES, training_paces
from pacechart.models import Athlete, Gender, average_5k_equivalent
from pacechart.scraper import ScheduledMeet

PaceKey = tuple[str, str]  # (zone label, display distance label)


def all_pace_keys() -> set[PaceKey]:
    return {(zone, dist) for zone in TRAINING_ZONES for dist in DISPLAY_DISTANCES_KM}


@dataclass
class AppState:
    athletes: dict[int, Athlete] = field(default_factory=dict)
    scheduled_meets: list[ScheduledMeet] = field(default_factory=list)

    # Which (zone, distance) combinations are enabled for the PDF/output.
    # Defaults to everything enabled (Design.md: "the full set available...
    # the user enables/disables individual ... combinations").
    enabled_paces: set[PaceKey] = field(default_factory=all_pace_keys)

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
        """Enabled (zone, distance) pairs in methodology order (zone by
        increasing intensity, distance from Mile down to 200m) — the
        column order used by both the GUI's Output tab and the PDF report."""
        zone_order = list(TRAINING_ZONES)
        dist_order = list(DISPLAY_DISTANCES_KM)
        return sorted(self.enabled_paces, key=lambda k: (zone_order.index(k[0]), dist_order.index(k[1])))

    def calculate(self) -> None:
        """Design.md workflow steps 3-4: average each athlete's selected
        results into a 5k-equivalent performance, then generate every
        enabled training pace from it. Athletes with no selected results
        get None in both dicts (workflow: "no results generate a row with
        no results, but not omit the athlete")."""
        self.computed_performance.clear()
        self.computed_paces.clear()

        for athlete_id, athlete in self.athletes.items():
            performance = average_5k_equivalent(athlete)
            self.computed_performance[athlete_id] = performance

            if performance is None:
                self.computed_paces[athlete_id] = None
                continue

            full_paces = training_paces(performance)
            self.computed_paces[athlete_id] = {
                (zone, dist): full_paces[zone][dist]
                for zone, dist in self.enabled_paces
            }
