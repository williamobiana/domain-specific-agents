class ConversionError(Exception):
    """Raised by pdf_converter when neither PDF library can extract usable text."""


class ParseError(Exception):
    """Raised by parser when no ExpenseItem objects are found in the Markdown."""


class GroupingError(Exception):
    """Raised by grouper for a structural/programming error (not for unmatched items)."""
