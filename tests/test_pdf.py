"""Tests for pacechart.pdf.generate_pdf.

reportlab's Table/Paragraph objects don't expose their rendered text in
a convenient way, so these tests exercise generate_pdf end-to-end and
assert on the produced file (it exists, is non-trivial, is a valid PDF)
rather than trying to parse reportlab internals.
"""

from datetime import date, datetime
from pathlib import Path

import pytest

from pacechart.app_state import AppState, Mode
from pacechart.models import Athlete, Gender, Meet, RaceResult
from pacechart.calculator import DISPLAY_DISTANCES_KM, TRAINING_ZONES
from pacechart.pdf import (
    _build_rows,
    estimated_table_width_pt,
    fits_one_page,
    fits_portrait,
    generate_pdf,
    needs_split_tables,
    usable_page_width_pt,
)


def make_meet(name="Meet", day=1) -> Meet:
    return Meet(name=name, date=date(2025, 9, day), location="Somewhere")


def build_state() -> AppState:
    boy_result = RaceResult(meet=make_meet(), distance_km=5.0, time_seconds=1200, selected=True)
    girl_result = RaceResult(meet=make_meet(), distance_km=5.0, time_seconds=1300, selected=True)
    boy = Athlete(name="Bob Smith", gender=Gender.BOYS, results=[boy_result])
    girl = Athlete(name="Gina Jones", gender=Gender.GIRLS, results=[girl_result])
    no_results = Athlete(name="Zed NoResult", gender=Gender.BOYS, results=[])

    state = AppState(athletes={1: boy, 2: girl, 3: no_results})
    state.calculate()
    return state


def test_generate_pdf_writes_a_valid_pdf_file(tmp_path: Path):
    state = build_state()
    output_path = tmp_path / "report.pdf"

    generate_pdf(state, str(output_path))

    assert output_path.exists()
    content = output_path.read_bytes()
    assert content.startswith(b"%PDF-")
    assert len(content) > 1000


def test_generate_pdf_works_with_no_enabled_paces(tmp_path: Path):
    # Athlete column only, no pace columns -- shouldn't crash.
    state = build_state()
    state.disable_all_paces()
    output_path = tmp_path / "empty_paces.pdf"

    generate_pdf(state, str(output_path))

    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"%PDF-")


def test_generate_pdf_works_with_no_athletes(tmp_path: Path):
    state = AppState()
    state.calculate()
    output_path = tmp_path / "empty.pdf"

    generate_pdf(state, str(output_path))

    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"%PDF-")


def test_build_rows_omits_5k_mark_column_by_default():
    state = build_state()

    rows = _build_rows(state, Gender.BOYS, state.sorted_enabled_paces())

    assert "5k Mark" not in rows[0]


def test_build_rows_includes_5k_mark_column_when_enabled():
    state = build_state()
    state.show_average_time_column = True

    rows = _build_rows(state, Gender.BOYS, state.sorted_enabled_paces())

    assert rows[0][1] == "5k Mark"
    by_name = {row[0]: row[1] for row in rows[1:]}
    assert by_name["Bob Smith"] == "19:18.6"
    assert by_name["Zed NoResult"] == ""


def test_fits_one_page_true_with_no_enabled_paces():
    state = build_state()
    state.disable_all_paces()
    assert fits_one_page(state)


def test_fits_one_page_false_with_every_pace_enabled():
    state = build_state()
    state.enable_all_paces()
    assert not fits_one_page(state)


def test_estimated_table_width_grows_with_more_enabled_paces():
    state = build_state()
    state.disable_all_paces()
    empty_width = estimated_table_width_pt(state)

    state.enable_all_paces()
    full_width = estimated_table_width_pt(state)

    assert full_width > empty_width
    assert usable_page_width_pt() > 0


def _enable_n_paces(state: AppState, n: int) -> None:
    state.disable_all_paces()
    keys = [(zone, dist) for zone in TRAINING_ZONES for dist in DISPLAY_DISTANCES_KM]
    for zone, dist in keys[:n]:
        state.set_pace_enabled(zone, dist, True)


def test_generate_pdf_uses_portrait_when_selection_fits(tmp_path: Path):
    from pypdf import PdfReader

    state = build_state()
    _enable_n_paces(state, 2)
    assert fits_portrait(state)
    output_path = tmp_path / "portrait.pdf"

    generate_pdf(state, str(output_path))

    page = PdfReader(str(output_path)).pages[0]
    box = page.mediabox
    assert float(box.width) < float(box.height)


def test_generate_pdf_switches_to_landscape_when_portrait_is_too_narrow(tmp_path: Path):
    from pypdf import PdfReader

    state = build_state()
    _enable_n_paces(state, 7)  # crosses the portrait width threshold but fits landscape
    assert not fits_portrait(state)
    assert fits_one_page(state)
    output_path = tmp_path / "landscape.pdf"

    generate_pdf(state, str(output_path))

    page = PdfReader(str(output_path)).pages[0]
    box = page.mediabox
    assert float(box.width) > float(box.height)


def test_generate_pdf_splits_into_two_tables_when_too_wide_for_landscape(tmp_path: Path):
    from pypdf import PdfReader

    state = build_state()
    _enable_n_paces(state, 10)  # crosses the landscape width threshold too
    assert not fits_portrait(state)
    assert needs_split_tables(state)
    assert fits_one_page(state)  # still handled -- via the two-table split
    output_path = tmp_path / "split.pdf"

    generate_pdf(state, str(output_path))

    reader = PdfReader(str(output_path))
    # One page per split table per gender: boys' first half, boys' second
    # half, girls' first half, girls' second half.
    assert len(reader.pages) == 4

    boys_page_1 = reader.pages[0].extract_text()
    boys_page_2 = reader.pages[1].extract_text()
    girls_page_1 = reader.pages[2].extract_text()

    # The new (second) table falls on its own page, and the athlete name
    # "carries over" onto it.
    assert "Bob Smith" in boys_page_1
    assert "Bob Smith" in boys_page_2
    assert "Gina Jones" not in boys_page_1
    assert "Gina Jones" not in boys_page_2
    assert "Gina Jones" in girls_page_1


def test_generate_pdf_footer_contains_the_export_timestamp(tmp_path: Path):
    from pypdf import PdfReader

    state = build_state()
    output_path = tmp_path / "timestamped.pdf"
    stamp = datetime(2026, 8, 18, 14, 30, 5)

    generate_pdf(state, str(output_path), generated_at=stamp)

    reader = PdfReader(str(output_path))
    first_page_text = reader.pages[0].extract_text()
    assert "Exported 2026-08-18 14:30:05" in first_page_text


def test_generate_pdf_footer_labels_the_mode(tmp_path: Path):
    from pypdf import PdfReader

    state = build_state()
    state.mode = Mode.TRACK
    state.calculate()
    output_path = tmp_path / "track.pdf"

    generate_pdf(state, str(output_path))

    reader = PdfReader(str(output_path))
    first_page_text = reader.pages[0].extract_text()
    assert "Track" in first_page_text
