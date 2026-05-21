import pytest

from src.errors import ConversionError, GroupingError, ParseError


class TestConversionError:
    def test_is_exception_subclass(self):
        assert issubclass(ConversionError, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ConversionError):
            raise ConversionError("could not extract text from PDF")

    def test_message_preserved(self):
        msg = "neither pdfplumber nor pdfminer produced text"
        exc = ConversionError(msg)
        assert str(exc) == msg

    def test_caught_as_exception(self):
        with pytest.raises(Exception):
            raise ConversionError("fallback also failed")

    def test_not_caught_as_parse_error(self):
        with pytest.raises(ConversionError):
            try:
                raise ConversionError("pdf error")
            except ParseError:
                pass  # should not reach here

    def test_empty_message(self):
        exc = ConversionError()
        assert str(exc) == ""

    def test_preserves_args(self):
        exc = ConversionError("detail", 42)
        assert exc.args == ("detail", 42)


class TestParseError:
    def test_is_exception_subclass(self):
        assert issubclass(ParseError, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ParseError):
            raise ParseError("no expense items found in markdown")

    def test_message_preserved(self):
        msg = "markdown contained no recognisable expense lines"
        exc = ParseError(msg)
        assert str(exc) == msg

    def test_caught_as_exception(self):
        with pytest.raises(Exception):
            raise ParseError("empty input")

    def test_not_caught_as_conversion_error(self):
        with pytest.raises(ParseError):
            try:
                raise ParseError("parse failed")
            except ConversionError:
                pass  # should not reach here

    def test_empty_message(self):
        exc = ParseError()
        assert str(exc) == ""

    def test_preserves_args(self):
        exc = ParseError("detail", 99)
        assert exc.args == ("detail", 99)


class TestGroupingError:
    def test_is_exception_subclass(self):
        assert issubclass(GroupingError, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(GroupingError):
            raise GroupingError("unexpected structural error in grouper")

    def test_message_preserved(self):
        msg = "schema inconsistency detected"
        exc = GroupingError(msg)
        assert str(exc) == msg

    def test_caught_as_exception(self):
        with pytest.raises(Exception):
            raise GroupingError("grouper bug")

    def test_not_caught_as_parse_error(self):
        with pytest.raises(GroupingError):
            try:
                raise GroupingError("grouper error")
            except ParseError:
                pass  # should not reach here

    def test_empty_message(self):
        exc = GroupingError()
        assert str(exc) == ""

    def test_preserves_args(self):
        exc = GroupingError("detail", True)
        assert exc.args == ("detail", True)


class TestExceptionDistinctness:
    def test_conversion_not_parse(self):
        assert ConversionError is not ParseError

    def test_conversion_not_grouping(self):
        assert ConversionError is not GroupingError

    def test_parse_not_grouping(self):
        assert ParseError is not GroupingError

    def test_conversion_not_instance_of_parse(self):
        exc = ConversionError("x")
        assert not isinstance(exc, ParseError)
        assert not isinstance(exc, GroupingError)

    def test_parse_not_instance_of_conversion(self):
        exc = ParseError("x")
        assert not isinstance(exc, ConversionError)
        assert not isinstance(exc, GroupingError)

    def test_grouping_not_instance_of_others(self):
        exc = GroupingError("x")
        assert not isinstance(exc, ConversionError)
        assert not isinstance(exc, ParseError)

    def test_all_are_exception_instances(self):
        for cls in (ConversionError, ParseError, GroupingError):
            assert isinstance(cls("msg"), Exception)
