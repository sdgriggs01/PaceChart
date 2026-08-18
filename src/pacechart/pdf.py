"""PDF report generation.

Design.md: "A PDF with a table per gender, where each athlete has a row
with the selected training paces. An athlete with no selected results
still gets a row; their pace cells are left blank rather than omitting
the athlete." Mirrors the GUI's Output tab (same column order, same
per-distance rounding), built from the same AppState.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, SimpleDocTemplate, Table, TableStyle

from pacechart.app_state import AppState, PaceKey
from pacechart.calculator import format_minutes, output_decimals_for
from pacechart.models import Gender

_HEADER_BACKGROUND = colors.HexColor("#333333")
_ALT_ROW_BACKGROUND = colors.whitesmoke

FONT_SIZE = 7
FOOTER_FONT_SIZE = 8
# reportlab Table's default LEFTPADDING + RIGHTPADDING (we don't override
# them), used to estimate rendered column widths for fits_one_page().
CELL_HORIZONTAL_PADDING_PT = 12
PAGE_MARGIN_INCH = 0.5


def _register_georgia() -> tuple[str, str]:
    """Registers the Georgia TrueType font (regular + bold) with reportlab
    if it's installed (standard on Windows), falling back to Helvetica on
    machines that don't have it (e.g. non-Windows)."""
    fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    regular_path = fonts_dir / "georgia.ttf"
    bold_path = fonts_dir / "georgiab.ttf"
    if regular_path.exists() and bold_path.exists():
        pdfmetrics.registerFont(TTFont("Georgia", str(regular_path)))
        pdfmetrics.registerFont(TTFont("Georgia-Bold", str(bold_path)))
        return "Georgia", "Georgia-Bold"
    return "Helvetica", "Helvetica-Bold"


FONT_NAME, FONT_BOLD_NAME = _register_georgia()


def usable_page_width_pt() -> float:
    """Printable width of one portrait letter page, inside the margins used by generate_pdf."""
    return letter[0] - 2 * PAGE_MARGIN_INCH * inch


def _build_rows(state: AppState, gender: Gender, pace_keys: list[PaceKey]) -> list[list[str]]:
    header = ["Athlete"] + [f"{zone}\n{dist}" for zone, dist in pace_keys]
    rows = [header]

    entries = sorted(
        (kv for kv in state.athletes.items() if kv[1].gender is gender),
        key=lambda kv: kv[1].name,
    )
    for athlete_id, athlete in entries:
        paces = state.computed_paces.get(athlete_id)
        row = [athlete.name]
        for zone, dist in pace_keys:
            if paces is None:
                row.append("")
            else:
                row.append(format_minutes(paces[(zone, dist)], decimals=output_decimals_for(dist)))
        rows.append(row)
    return rows


def _table_from_rows(rows: list[list[str]]) -> Table:
    table = Table(rows, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD_NAME),
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BACKGROUND),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), FONT_SIZE),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ALT_ROW_BACKGROUND]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    return table


def _estimate_rows_width_pt(rows: list[list[str]]) -> float:
    """Estimate a table's rendered width: for each column, the widest single
    line of text (headers wrap to two lines, and render bold) at FONT_SIZE,
    plus reportlab's default cell padding, summed across columns."""
    if not rows:
        return 0.0
    num_cols = len(rows[0])
    column_widths = [0.0] * num_cols
    for row_index, row in enumerate(rows):
        font = FONT_BOLD_NAME if row_index == 0 else FONT_NAME
        for col, cell in enumerate(row):
            for line in str(cell).split("\n"):
                width = stringWidth(line, font, FONT_SIZE)
                if width > column_widths[col]:
                    column_widths[col] = width
    return sum(w + CELL_HORIZONTAL_PADDING_PT for w in column_widths)


def estimated_table_width_pt(state: AppState) -> float:
    """The wider of the two gender tables' estimated rendered widths — used
    to warn the user before a pace selection that won't fit one printed page."""
    pace_keys = state.sorted_enabled_paces()
    widths = [_estimate_rows_width_pt(_build_rows(state, gender, pace_keys)) for gender in (Gender.BOYS, Gender.GIRLS)]
    return max(widths, default=0.0)


def fits_one_page(state: AppState) -> bool:
    return estimated_table_width_pt(state) <= usable_page_width_pt()


def _footer_drawer(generated_at: datetime):
    text = f"Exported {generated_at.strftime('%Y-%m-%d %H:%M:%S')}"

    def draw_footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont(FONT_NAME, FOOTER_FONT_SIZE)
        canvas.drawRightString(letter[0] - PAGE_MARGIN_INCH * inch, 0.3 * inch, text)
        canvas.restoreState()

    return draw_footer


def generate_pdf(state: AppState, output_path: str, generated_at: datetime | None = None) -> None:
    """Writes the PDF to `output_path`, one gender per sheet (page), with
    the export time stamped in the footer of every page."""
    if generated_at is None:
        generated_at = datetime.now()

    pace_keys = state.sorted_enabled_paces()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=PAGE_MARGIN_INCH * inch,
        rightMargin=PAGE_MARGIN_INCH * inch,
        topMargin=PAGE_MARGIN_INCH * inch,
        bottomMargin=PAGE_MARGIN_INCH * inch,
    )

    genders = (Gender.BOYS, Gender.GIRLS)
    elements = []
    for index, gender in enumerate(genders):
        elements.append(_table_from_rows(_build_rows(state, gender, pace_keys)))
        if index < len(genders) - 1:
            elements.append(PageBreak())

    footer = _footer_drawer(generated_at)
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
