import csv

import pytest

from src.grouper import CategorisedItem
from src.summariser import compute_grand_totals, summarise
from src.writer import _fmt, write_csv


def _build(items):
    summaries = summarise(items)
    ti, te = compute_grand_totals(summaries)
    return summaries, ti, te


def _rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


class TestFmt:
    def test_integer(self):
        assert _fmt(100) == "100.00"

    def test_one_decimal(self):
        assert _fmt(3.5) == "3.50"

    def test_two_decimals(self):
        assert _fmt(1234.56) == "1234.56"

    def test_zero(self):
        assert _fmt(0.0) == "0.00"

    def test_large_amount(self):
        assert _fmt(99999.99) == "99999.99"


class TestWriteCsv:
    def test_header_row(self, tmp_path):
        out = str(tmp_path / "out.csv")
        write_csv(*_build([]), out)
        assert _rows(out)[0] == ["section", "category", "total_amount"]

    def test_all_rows_have_three_columns(self, tmp_path):
        out = str(tmp_path / "out.csv")
        write_csv(*_build([]), out)
        assert all(len(r) == 3 for r in _rows(out))

    def test_category_row_content(self, tmp_path):
        items = [CategorisedItem(section="Regular Inflows", category="Salary", amount=3500.0)]
        out = str(tmp_path / "out.csv")
        write_csv(*_build(items), out)
        rows = _rows(out)
        salary_rows = [r for r in rows if r[1] == "Salary"]
        assert salary_rows == [["Regular Inflows", "Salary", "3500.00"]]

    def test_subtotal_row_per_section(self, tmp_path):
        items = [CategorisedItem(section="Regular Inflows", category="Salary", amount=1000.0)]
        out = str(tmp_path / "out.csv")
        write_csv(*_build(items), out)
        rows = _rows(out)
        subtotal = [r for r in rows if r[0] == "Regular Inflows" and r[1] == "Subtotal"]
        assert subtotal == [["Regular Inflows", "Subtotal", "1000.00"]]

    def test_subtotal_row_present_for_every_schema_section(self, tmp_path):
        out = str(tmp_path / "out.csv")
        write_csv(*_build([]), out)
        rows = _rows(out)
        from src.categories import SCHEMA
        for section in SCHEMA:
            subtotals = [r for r in rows if r[0] == section.name and r[1] == "Subtotal"]
            assert len(subtotals) == 1, f"Missing subtotal for {section.name}"

    def test_total_income_row(self, tmp_path):
        items = [CategorisedItem(section="Regular Inflows", category="Salary", amount=3500.0)]
        out = str(tmp_path / "out.csv")
        write_csv(*_build(items), out)
        rows = _rows(out)
        income_rows = [r for r in rows if r[1] == "Total Income"]
        assert income_rows == [["", "Total Income", "3500.00"]]

    def test_total_expenditure_row(self, tmp_path):
        items = [CategorisedItem(section="Regular Outflows", category="Rent", amount=900.0)]
        out = str(tmp_path / "out.csv")
        write_csv(*_build(items), out)
        rows = _rows(out)
        exp_rows = [r for r in rows if r[1] == "Total Expenditure"]
        assert exp_rows == [["", "Total Expenditure", "900.00"]]

    def test_total_income_before_total_expenditure(self, tmp_path):
        out = str(tmp_path / "out.csv")
        write_csv(*_build([]), out)
        rows = _rows(out)
        income_idx = next(i for i, r in enumerate(rows) if r[1] == "Total Income")
        exp_idx = next(i for i, r in enumerate(rows) if r[1] == "Total Expenditure")
        assert income_idx < exp_idx

    def test_income_sections_before_total_income(self, tmp_path):
        out = str(tmp_path / "out.csv")
        write_csv(*_build([]), out)
        rows = _rows(out)
        income_idx = next(i for i, r in enumerate(rows) if r[1] == "Total Income")
        for section_name in ["Regular Inflows", "Irregular Inflows", "Asset Liquidation"]:
            section_row_idxs = [i for i, r in enumerate(rows) if r[0] == section_name]
            assert all(i < income_idx for i in section_row_idxs)

    def test_outflow_sections_before_total_expenditure(self, tmp_path):
        out = str(tmp_path / "out.csv")
        write_csv(*_build([]), out)
        rows = _rows(out)
        exp_idx = next(i for i, r in enumerate(rows) if r[1] == "Total Expenditure")
        for section_name in ["Regular Outflows", "Irregular Outflows", "Assets"]:
            section_row_idxs = [i for i, r in enumerate(rows) if r[0] == section_name]
            assert all(i < exp_idx for i in section_row_idxs)

    def test_uncategorised_appended_after_total_expenditure(self, tmp_path):
        items = [
            CategorisedItem(section="Uncategorised", category="Uncategorised", amount=50.0),
        ]
        out = str(tmp_path / "out.csv")
        write_csv(*_build(items), out)
        rows = _rows(out)
        exp_idx = next(i for i, r in enumerate(rows) if r[1] == "Total Expenditure")
        unc_idxs = [i for i, r in enumerate(rows) if r[0] == "Uncategorised"]
        assert len(unc_idxs) > 0
        assert all(i > exp_idx for i in unc_idxs)

    def test_no_uncategorised_rows_when_absent(self, tmp_path):
        items = [CategorisedItem(section="Regular Inflows", category="Salary", amount=1000.0)]
        out = str(tmp_path / "out.csv")
        write_csv(*_build(items), out)
        rows = _rows(out)
        assert not any(r[0] == "Uncategorised" for r in rows)

    def test_zero_amounts_formatted(self, tmp_path):
        out = str(tmp_path / "out.csv")
        write_csv(*_build([]), out)
        rows = _rows(out)
        salary_rows = [r for r in rows if r[1] == "Salary"]
        assert salary_rows[0][2] == "0.00"

    def test_utf8_encoding(self, tmp_path):
        out = str(tmp_path / "out.csv")
        write_csv(*_build([]), out)
        with open(out, "rb") as f:
            f.read().decode("utf-8")

    def test_multiple_income_sections_total(self, tmp_path):
        items = [
            CategorisedItem(section="Regular Inflows", category="Salary", amount=3000.0),
            CategorisedItem(section="Irregular Inflows", category="Loan", amount=500.0),
            CategorisedItem(section="Asset Liquidation", category="Savings", amount=200.0),
        ]
        out = str(tmp_path / "out.csv")
        write_csv(*_build(items), out)
        rows = _rows(out)
        income_row = next(r for r in rows if r[1] == "Total Income")
        assert income_row[2] == "3700.00"

    def test_multiple_outflow_sections_total(self, tmp_path):
        items = [
            CategorisedItem(section="Regular Outflows", category="Rent", amount=900.0),
            CategorisedItem(section="Irregular Outflows", category="Eating Out", amount=150.0),
            CategorisedItem(section="Assets", category="Active Savings", amount=400.0),
        ]
        out = str(tmp_path / "out.csv")
        write_csv(*_build(items), out)
        rows = _rows(out)
        exp_row = next(r for r in rows if r[1] == "Total Expenditure")
        assert exp_row[2] == "1450.00"

    def test_uncategorised_subtotal_row(self, tmp_path):
        items = [
            CategorisedItem(section="Uncategorised", category="Uncategorised", amount=12.50),
            CategorisedItem(section="Uncategorised", category="Uncategorised", amount=4.80),
        ]
        out = str(tmp_path / "out.csv")
        write_csv(*_build(items), out)
        rows = _rows(out)
        unc_subtotal = [r for r in rows if r[0] == "Uncategorised" and r[1] == "Subtotal"]
        assert len(unc_subtotal) == 1
        assert unc_subtotal[0][2] == pytest.approx("17.30", abs=0.005)
