class ConversionError(Exception):
    """Raised when a general conversion error occurs."""
    pass

class ParseError(Exception):
    """Raised when parsing of content fails."""
    pass

class GroupingError(Exception):
    """Raised when grouping or structuring data fails."""
    pass
