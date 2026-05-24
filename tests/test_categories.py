import pytest

from src.categories import INCOME_SECTIONS, OUTFLOW_SECTIONS, SCHEMA, Section


class TestSectionDataclass:
    def test_section_is_frozen(self):
        section = Section(name="Test", categories=["A"])
        with pytest.raises(Exception):
            section.name = "Changed"  # type: ignore[misc]

    def test_section_stores_name_and_categories(self):
        section = Section(name="My Section", categories=["Cat A", "Cat B"])
        assert section.name == "My Section"
        assert section.categories == ["Cat A", "Cat B"]

    def test_section_equality(self):
        s1 = Section(name="X", categories=["A"])
        s2 = Section(name="X", categories=["A"])
        assert s1 == s2

    def test_section_inequality(self):
        s1 = Section(name="X", categories=["A"])
        s2 = Section(name="Y", categories=["A"])
        assert s1 != s2


class TestSchema:
    def test_schema_has_six_sections(self):
        assert len(SCHEMA) == 6

    def test_schema_section_order(self):
        names = [s.name for s in SCHEMA]
        assert names == [
            "Regular Inflows",
            "Irregular Inflows",
            "Asset Liquidation",
            "Regular Outflows",
            "Irregular Outflows",
            "Assets",
        ]

    def test_regular_inflows_categories(self):
        section = next(s for s in SCHEMA if s.name == "Regular Inflows")
        assert section.categories == ["Salary"]

    def test_irregular_inflows_categories(self):
        section = next(s for s in SCHEMA if s.name == "Irregular Inflows")
        assert section.categories == ["Carry Over", "Unexpected / Refund", "Loan"]

    def test_asset_liquidation_categories(self):
        section = next(s for s in SCHEMA if s.name == "Asset Liquidation")
        assert section.categories == ["Savings", "Stocks & Shares"]

    def test_regular_outflows_categories(self):
        section = next(s for s in SCHEMA if s.name == "Regular Outflows")
        assert section.categories == [
            "Rent", "Bill - Council Tax", "Bill - Electricity & Gas",
            "Bill - Phone & Internet", "Food Supplies", "Debt", "Car & Gas",
        ]

    def test_irregular_outflows_categories(self):
        section = next(s for s in SCHEMA if s.name == "Irregular Outflows")
        assert section.categories == [
            "Charity / Donations", "Gifts Entertainment & Misc",
            "Sundry", "Holidays & Travel", "Education", "Eating Out",
        ]

    def test_assets_categories(self):
        section = next(s for s in SCHEMA if s.name == "Assets")
        assert section.categories == [
            "Active Savings", "Lifetime ISA", "Stocks & Shares ISA", "Dividend Portfolio",
        ]

    def test_all_sections_are_section_instances(self):
        for section in SCHEMA:
            assert isinstance(section, Section)

    def test_all_sections_have_nonempty_categories(self):
        for section in SCHEMA:
            assert len(section.categories) > 0

    def test_no_duplicate_section_names(self):
        names = [s.name for s in SCHEMA]
        assert len(names) == len(set(names))

    def test_no_duplicate_categories_within_section(self):
        for section in SCHEMA:
            assert len(section.categories) == len(set(section.categories))


class TestIncomeSections:
    def test_income_sections_order(self):
        assert INCOME_SECTIONS == ["Regular Inflows", "Irregular Inflows", "Asset Liquidation"]

    def test_income_section_names_exist_in_schema(self):
        schema_names = {s.name for s in SCHEMA}
        for name in INCOME_SECTIONS:
            assert name in schema_names

    def test_income_sections_count(self):
        assert len(INCOME_SECTIONS) == 3


class TestOutflowSections:
    def test_outflow_sections_order(self):
        assert OUTFLOW_SECTIONS == ["Regular Outflows", "Irregular Outflows", "Assets"]

    def test_outflow_section_names_exist_in_schema(self):
        schema_names = {s.name for s in SCHEMA}
        for name in OUTFLOW_SECTIONS:
            assert name in schema_names

    def test_outflow_sections_count(self):
        assert len(OUTFLOW_SECTIONS) == 3


class TestIncomOutflowPartition:
    def test_no_section_in_both_income_and_outflow(self):
        overlap = set(INCOME_SECTIONS) & set(OUTFLOW_SECTIONS)
        assert overlap == set()

    def test_income_and_outflow_cover_all_schema_sections(self):
        all_named = set(INCOME_SECTIONS) | set(OUTFLOW_SECTIONS)
        schema_names = {s.name for s in SCHEMA}
        assert all_named == schema_names
