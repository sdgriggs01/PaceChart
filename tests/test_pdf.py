"""Tests for pacechart.pdf.generate_pdf.

reportlab's Table/Paragraph objects don't expose their rendered text in
a convenient way, so these tests exercise generate_pdf end-to-end and
assert on the produced file (it exists, is non-trivial, is a valid PDF)
rather than trying to parse reportlab internals.
"""

from datetime import date, datetime
from pathlib import Path

import pytest

from pacechart.app_state import AppState
from pacechart.models import Athlete, Gender, Meet, RaceResult
from pacechart.pdf import estimated_table_width_pt, fits_one_page, generate_pdf, usable_page_width_pt


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


def test_generate_pdf_footer_contains_the_export_timestamp(tmp_path: Path):
    from pypdf import PdfReader

    state = build_state()
    output_path = tmp_path / "timestamped.pdf"
    stamp = datetime(2026, 8, 18, 14, 30, 5)

    generate_pdf(state, str(output_path), generated_at=stamp)

    reader = PdfReader(str(output_path))
    first_page_text = reader.pages[0].extract_text()
    assert "Exported 2026-08-18 14:30:05" in first_page_text
