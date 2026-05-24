import pytest

from src.errors import ParseError
from src.parser import ExpenseItem, _normalise_amount, _parse_line, parse_items


SAMPLE_MD = """\
Salary £3,500.00
Rent 900.00
Unknown item £12.50
not a valid line
"""


class TestNormaliseAmount:
    def test_gbp_with_comma(self):
        assert _normalise_amount("£3,500.00") == 3500.0

    def test_usd_no_decimal(self):
        assert _normalise_amount("$1,200") == 1200.0

    def test_eur_with_space(self):
        assert _normalise_amount("€ 99.9") == pytest.approx(99.9)

    def test_bare_integer(self):
        assert _normalise_amount("42") == 42.0

    def test_bare_float(self):
        assert _normalise_amount("1234.56") == pytest.approx(1234.56)

    def test_raises_value_error_on_empty(self):
        with pytest.raises(ValueError):
            _normalise_amount("")

    def test_raises_value_error_on_symbol_only(self):
        with pytest.raises(ValueError):
            _normalise_amount("£")

    def test_raises_value_error_on_text(self):
        with pytest.raises(ValueError):
            _normalise_amount("abc")

    def test_comma_thousands_multi(self):
        assert _normalise_amount("1,000,000.00") == 1000000.0

    def test_gbp_no_decimal(self):
        assert _normalise_amount("£500") == 500.0

    def test_eur_no_space(self):
        assert _normalise_amount("€99.99") == pytest.approx(99.99)


class TestParseLine:
    def test_amount_after_description(self):
        item = _parse_line("Salary £3,500.00")
        assert item is not None
        assert item.raw_text == "Salary"
        assert item.amount == 3500.0

    def test_amount_without_currency(self):
        item = _parse_line("Rent 900.00")
        assert item is not None
        assert item.raw_text == "Rent"
        assert item.amount == 900.0

    def test_amount_before_description(self):
        item = _parse_line("£12.50 Unknown item")
        assert item is not None
        assert item.amount == 12.50
        assert item.raw_text == "Unknown item"

    def test_no_amount_returns_none(self):
        assert _parse_line("not a valid line") is None

    def test_empty_line_returns_none(self):
        assert _parse_line("") is None

    def test_amount_only_returns_none(self):
        assert _parse_line("£3,500.00") is None

    def test_description_stripped_of_whitespace(self):
        item = _parse_line("  Salary   £3,500.00  ")
        assert item is not None
        assert item.raw_text == "Salary"

    def test_gbp_symbol_handled(self):
        item = _parse_line("Food £45.99")
        assert item is not None
        assert item.amount == pytest.approx(45.99)

    def test_usd_symbol_handled(self):
        item = _parse_line("Subscription $9.99")
        assert item is not None
        assert item.amount == pytest.approx(9.99)

    def test_eur_symbol_handled(self):
        item = _parse_line("Holiday €250.00")
        assert item is not None
        assert item.amount == 250.0

    def test_returns_expense_item_type(self):
        item = _parse_line("Salary £100")
        assert isinstance(item, ExpenseItem)

    def test_multi_word_description(self):
        item = _parse_line("Bill - Council Tax £180.00")
        assert item is not None
        assert "Bill" in item.raw_text
        assert item.amount == 180.0


class TestParseItems:
    def test_three_valid_one_invalid_returns_three(self):
        items = parse_items(SAMPLE_MD)
        assert len(items) == 3

    def test_returns_expense_item_instances(self):
        items = parse_items(SAMPLE_MD)
        assert all(isinstance(i, ExpenseItem) for i in items)

    def test_amounts_are_floats(self):
        items = parse_items(SAMPLE_MD)
        assert all(isinstance(i.amount, float) for i in items)

    def test_raises_parse_error_on_empty_string(self):
        with pytest.raises(ParseError):
            parse_items("")

    def test_raises_parse_error_on_no_amounts(self):
        with pytest.raises(ParseError):
            parse_items("no amounts here\nanother blank line")

    def test_raises_parse_error_on_whitespace_only(self):
        with pytest.raises(ParseError):
            parse_items("   \n  \n  ")

    def test_invalid_lines_skipped_silently(self):
        md = "Valid item £10.00\njust words no number\nAnother £5.00"
        items = parse_items(md)
        assert len(items) == 2

    def test_gbp_currency_handled(self):
        items = parse_items("Salary £3,500.00")
        assert items[0].amount == 3500.0

    def test_usd_currency_handled(self):
        items = parse_items("Salary $3,500.00")
        assert items[0].amount == 3500.0

    def test_eur_currency_handled(self):
        items = parse_items("Salary €3,500.00")
        assert items[0].amount == 3500.0

    def test_descriptions_preserved(self):
        items = parse_items(SAMPLE_MD)
        descriptions = {i.raw_text for i in items}
        assert "Salary" in descriptions
        assert "Rent" in descriptions

    def test_single_valid_line(self):
        items = parse_items("Rent £900")
        assert len(items) == 1
        assert items[0].raw_text == "Rent"
        assert items[0].amount == 900.0

    def test_comma_in_amount(self):
        items = parse_items("Salary £3,500.00")
        assert items[0].amount == 3500.0

    def test_line_with_only_number_skipped(self):
        with pytest.raises(ParseError):
            parse_items("£3500.00")

    def test_parse_error_is_exception(self):
        with pytest.raises(Exception):
            parse_items("")
