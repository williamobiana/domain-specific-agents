import pytest
from src.categories import SCHEMA, INCOME_SECTIONS, OUTFLOW_SECTIONS, Section


class TestCategoriesSchema:
    """Test the canonical category schema definition"""
    
    def test_schema_contains_exactly_6_sections(self):
        """Assert SCHEMA contains exactly 6 sections"""
        assert len(SCHEMA) == 6, f"Expected 6 sections, got {len(SCHEMA)}"
    
    def test_schema_has_correct_section_names(self):
        """Assert section names match the expected order"""
        expected_names = [
            "Regular Inflows",
            "Irregular Inflows", 
            "Asset Liquidation",
            "Regular Outflows",
            "Irregular Outflows",
            "Assets"
        ]
        actual_names = [section.name for section in SCHEMA]
        assert actual_names == expected_names, f"Expected {expected_names}, got {actual_names}"
    
    def test_regular_inflows_categories(self):
        """Test Regular Inflows section has exactly 'Salary'"""
        section = SCHEMA[0]
        assert section.name == "Regular Inflows"
        assert section.categories == ["Salary"]
        assert len(section.categories) == 1
    
    def test_irregular_inflows_categories(self):
        """Test Irregular Inflows section has 3 categories"""
        section = SCHEMA[1]
        assert section.name == "Irregular Inflows"
        expected = ["Carry Over", "Unexpected / Refund", "Loan"]
        assert section.categories == expected
        assert len(section.categories) == 3
    
    def test_asset_liquidation_categories(self):
        """Test Asset Liquidation section has 2 categories"""
        section = SCHEMA[2]
        assert section.name == "Asset Liquidation"
        expected = ["Savings", "Stocks & Shares"]
        assert section.categories == expected
        assert len(section.categories) == 2
    
    def test_regular_outflows_categories(self):
        """Test Regular Outflows section has 7 categories"""
        section = SCHEMA[3]
        assert section.name == "Regular Outflows"
        expected = [
            "Rent",
            "Bill - Council Tax",
            "Bill - Electricity & Gas",
            "Bill - Phone & Internet",
            "Food Supplies",
            "Debt",
            "Car & Gas"
        ]
        assert section.categories == expected
        assert len(section.categories) == 7
    
    def test_irregular_outflows_categories(self):
        """Test Irregular Outflows section has 6 categories"""
        section = SCHEMA[4]
        assert section.name == "Irregular Outflows"
        expected = [
            "Charity / Donations",
            "Gifts, Entertainment & Misc",
            "Sundry",
            "Holidays & Travel",
            "Education",
            "Eating Out"
        ]
        assert section.categories == expected
        assert len(section.categories) == 6
    
    def test_assets_categories(self):
        """Test Assets section has 4 categories"""
        section = SCHEMA[5]
        assert section.name == "Assets"
        expected = [
            "Active Savings",
            "Lifetime ISA",
            "Stocks & Shares ISA",
            "Dividend Portfolio"
        ]
        assert section.categories == expected
        assert len(section.categories) == 4
    
    def test_total_categories_count(self):
        """Assert total number of categories across all sections is 21"""
        total_categories = sum(len(section.categories) for section in SCHEMA)
        assert total_categories == 23, f"Expected 23 total categories, got {total_categories}"
    
    def test_income_sections_contains_3_sections(self):
        """Assert INCOME_SECTIONS contains exactly 3 section names"""
        assert len(INCOME_SECTIONS) == 3
        expected = ["Regular Inflows", "Irregular Inflows", "Asset Liquidation"]
        assert INCOME_SECTIONS == expected
    
    def test_outflow_sections_contains_3_sections(self):
        """Assert OUTFLOW_SECTIONS contains exactly 3 section names"""
        assert len(OUTFLOW_SECTIONS) == 3
        expected = ["Regular Outflows", "Irregular Outflows", "Assets"]
        assert OUTFLOW_SECTIONS == expected
    
    def test_section_lists_cover_all_sections(self):
        """Assert INCOME_SECTIONS and OUTFLOW_SECTIONS together cover all section names"""
        all_section_names = set(section.name for section in SCHEMA)
        covered_names = set(INCOME_SECTIONS + OUTFLOW_SECTIONS)
        assert covered_names == all_section_names, \
            f"Covered {covered_names}, but sections are {all_section_names}"
    
    def test_section_lists_have_no_overlap(self):
        """Assert INCOME_SECTIONS and OUTFLOW_SECTIONS have no common sections"""
        overlap = set(INCOME_SECTIONS) & set(OUTFLOW_SECTIONS)
        assert len(overlap) == 0, f"Found overlapping sections: {overlap}"
    
    def test_each_category_name_is_unique_across_schema(self):
        """Optional: Assert no duplicate category names across different sections"""
        all_categories = []
        for section in SCHEMA:
            all_categories.extend(section.categories)
        assert len(all_categories) == len(set(all_categories)), \
            "Duplicate category names found across sections"
