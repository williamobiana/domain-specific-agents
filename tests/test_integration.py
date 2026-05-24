from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from src.main import main, run_pipeline


def _make_fixture_pdf(path: str) -> None:
    """Create a minimal PDF with recognisable expense lines using reportlab."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(path, pagesize=letter)
    c.drawString(72, 720, "Salary 3500.00")
    c.drawString(72, 700, "Rent 900.00")
    c.drawString(72, 680, "Food Supplies 150.00")
    c.save()


@pytest.fixture
def fixture_pdf(tmp_path):
    pdf_path = str(tmp_path / "fixture.pdf")
    _make_fixture_pdf(pdf_path)
    return pdf_path


class TestIntegrationRunPipeline:
    def test_output_csv_is_created(self, fixture_pdf, tmp_path):
        output_csv = str(tmp_path / "output.csv")
        run_pipeline(fixture_pdf, output_csv)
        assert os.path.exists(output_csv)

    def test_csv_has_header_row(self, fixture_pdf, tmp_path):
        output_csv = str(tmp_path / "output.csv")
        run_pipeline(fixture_pdf, output_csv)
        with open(output_csv, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f))
        assert header == ["section", "category", "total_amount"]

    def test_csv_contains_total_income_row(self, fixture_pdf, tmp_path):
        output_csv = str(tmp_path / "output.csv")
        run_pipeline(fixture_pdf, output_csv)
        with open(output_csv, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert any("Total Income" in row for row in rows)

    def test_csv_contains_total_expenditure_row(self, fixture_pdf, tmp_path):
        output_csv = str(tmp_path / "output.csv")
        run_pipeline(fixture_pdf, output_csv)
        with open(output_csv, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert any("Total Expenditure" in row for row in rows)

    def test_salary_amount_reflected_in_csv(self, fixture_pdf, tmp_path):
        output_csv = str(tmp_path / "output.csv")
        run_pipeline(fixture_pdf, output_csv)
        content = Path(output_csv).read_text(encoding="utf-8")
        assert "3500.00" in content

    def test_no_temp_files_remain_after_pipeline(self, fixture_pdf, tmp_path):
        output_csv = str(tmp_path / "output.csv")
        import tempfile

        before = set(Path(tempfile.gettempdir()).glob("*.md"))
        run_pipeline(fixture_pdf, output_csv)
        after = set(Path(tempfile.gettempdir()).glob("*.md"))
        assert after == before


class TestIntegrationMainExitBehaviour:
    def test_main_exits_zero_on_valid_input(self, fixture_pdf, tmp_path):
        output_csv = str(tmp_path / "output.csv")
        with patch("sys.argv", ["expense-summary", fixture_pdf, output_csv]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 0

    def test_main_creates_csv_on_valid_input(self, fixture_pdf, tmp_path):
        output_csv = str(tmp_path / "output.csv")
        with patch("sys.argv", ["expense-summary", fixture_pdf, output_csv]):
            with pytest.raises(SystemExit):
                main()
        assert os.path.exists(output_csv)
