import pytest

from src.categories import INCOME_SECTIONS, OUTFLOW_SECTIONS, SCHEMA
from src.grouper import CategorisedItem
from src.summariser import CategoryTotal, SectionSummary, compute_grand_totals, summarise


class TestBuildCategoryTotals:
    def test_single_item_salary(self):
        items = [CategorisedItem(section="Regular Inflows", category="Salary", amount=3500.0)]
        summaries = summarise(items)
        ri = next(s for s in summaries if s.section == "Regular Inflows")
        salary_total = next(ct for ct in ri.categories if ct.category == "Salary")
        assert salary_total.total == 3500.0

    def test_two_items_same_category_sum(self):
        items = [
            CategorisedItem(section="Regular Inflows", category="Salary", amount=3500.0),
            CategorisedItem(section="Regular Inflows", category="Salary", amount=200.0),
        ]
        summaries = summarise(items)
        ri = next(s for s in summaries if s.section == "Regular Inflows")
        salary_total = next(ct for ct in ri.categories if ct.category == "Salary")
        assert salary_total.total == 3700.0

    def test_zero_filled_for_missing_category(self):
        items = [CategorisedItem(section="Regular Inflows", category="Salary", amount=1000.0)]
        summaries = summarise(items)
        # "Irregular Inflows" has no items — all its categories should be 0
        ii = next(s for s in summaries if s.section == "Irregular Inflows")
        for ct in ii.categories:
            assert ct.total == 0.0


class TestSummarise:
    def test_all_schema_sections_present(self):
        summaries = summarise([])
        section_names = [s.section for s in summaries]
        for section in SCHEMA:
            assert section.name in section_names

    def test_all_canonical_categories_present_per_section(self):
        summaries = summarise([])
        for section in SCHEMA:
            summary = next(s for s in summaries if s.section == section.name)
            summary_cats = [ct.category for ct in summary.categories]
            assert summary_cats == section.categories

    def test_subtotal_single_item(self):
        items = [CategorisedItem(section="Regular Inflows", category="Salary", amount=3500.0)]
        summaries = summarise(items)
        ri = next(s for s in summaries if s.section == "Regular Inflows")
        assert ri.subtotal == 3500.0

    def test_subtotal_multiple_items_different_categories(self):
        items = [
            CategorisedItem(section="Irregular Inflows", category="Carry Over", amount=100.0),
            CategorisedItem(section="Irregular Inflows", category="Loan", amount=500.0),
        ]
        summaries = summarise(items)
        ii = next(s for s in summaries if s.section == "Irregular Inflows")
        assert ii.subtotal == 600.0

    def test_empty_items_all_sections_zero(self):
        summaries = summarise([])
        for summary in summaries:
            assert summary.subtotal == 0.0

    def test_returns_list_of_section_summary(self):
        summaries = summarise([])
        assert all(isinstance(s, SectionSummary) for s in summaries)

    def test_uncategorised_appended_when_present(self):
        items = [CategorisedItem(section="Uncategorised", category="Uncategorised", amount=50.0)]
        summaries = summarise(items)
        assert summaries[-1].section == "Uncategorised"

    def test_uncategorised_not_appended_when_absent(self):
        items = [CategorisedItem(section="Regular Inflows", category="Salary", amount=1000.0)]
        summaries = summarise(items)
        section_names = [s.section for s in summaries]
        assert "Uncategorised" not in section_names

    def test_uncategorised_subtotal(self):
        items = [
            CategorisedItem(section="Uncategorised", category="Uncategorised", amount=12.50),
            CategorisedItem(section="Uncategorised", category="Uncategorised", amount=4.80),
        ]
        summaries = summarise(items)
        unc = next(s for s in summaries if s.section == "Uncategorised")
        assert unc.subtotal == pytest.approx(17.30)

    def test_section_order_follows_schema(self):
        summaries = summarise([])
        schema_names = [s.name for s in SCHEMA]
        summary_names = [s.section for s in summaries if s.section != "Uncategorised"]
        assert summary_names == schema_names


class TestComputeGrandTotals:
    def test_income_sections_summed(self):
        items = [
            CategorisedItem(section="Regular Inflows", category="Salary", amount=3500.0),
            CategorisedItem(section="Irregular Inflows", category="Loan", amount=200.0),
        ]
        summaries = summarise(items)
        total_income, _ = compute_grand_totals(summaries)
        assert total_income == pytest.approx(3700.0)

    def test_outflow_sections_summed(self):
        items = [
            CategorisedItem(section="Regular Outflows", category="Rent", amount=900.0),
            CategorisedItem(section="Irregular Outflows", category="Eating Out", amount=150.0),
        ]
        summaries = summarise(items)
        _, total_expenditure = compute_grand_totals(summaries)
        assert total_expenditure == pytest.approx(1050.0)

    def test_income_and_expenditure_independent(self):
        items = [
            CategorisedItem(section="Regular Inflows", category="Salary", amount=3500.0),
            CategorisedItem(section="Regular Outflows", category="Rent", amount=900.0),
        ]
        summaries = summarise(items)
        total_income, total_expenditure = compute_grand_totals(summaries)
        assert total_income == pytest.approx(3500.0)
        assert total_expenditure == pytest.approx(900.0)

    def test_empty_summaries(self):
        summaries = summarise([])
        total_income, total_expenditure = compute_grand_totals(summaries)
        assert total_income == 0.0
        assert total_expenditure == 0.0

    def test_uncategorised_excluded_from_grand_totals(self):
        items = [
            CategorisedItem(section="Uncategorised", category="Uncategorised", amount=999.0),
        ]
        summaries = summarise(items)
        total_income, total_expenditure = compute_grand_totals(summaries)
        assert total_income == 0.0
        assert total_expenditure == 0.0

    def test_all_income_sections_included(self):
        items = [
            CategorisedItem(section="Regular Inflows", category="Salary", amount=1000.0),
            CategorisedItem(section="Irregular Inflows", category="Carry Over", amount=200.0),
            CategorisedItem(section="Asset Liquidation", category="Savings", amount=500.0),
        ]
        summaries = summarise(items)
        total_income, _ = compute_grand_totals(summaries)
        assert total_income == pytest.approx(1700.0)

    def test_all_outflow_sections_included(self):
        items = [
            CategorisedItem(section="Regular Outflows", category="Rent", amount=900.0),
            CategorisedItem(section="Irregular Outflows", category="Education", amount=300.0),
            CategorisedItem(section="Assets", category="Active Savings", amount=400.0),
        ]
        summaries = summarise(items)
        _, total_expenditure = compute_grand_totals(summaries)
        assert total_expenditure == pytest.approx(1600.0)
