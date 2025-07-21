from edgy.exceptions import EdgyException


class InvalidModelError(EdgyException):
    """
    Exception raised when an invalid model operation or definition is encountered.

    This error typically indicates that a model is being used in a way that is
    not permitted by Edgy's ORM rules, or that the model's definition itself
    is incorrect or incomplete for the intended operation. It inherits from
    `EdgyException`, making it part of Edgy's custom exception hierarchy.
    """

    ...


class ExcludeValue(BaseException):
    """
    Special exception used internally to signal that a value should be excluded.

    This exception is a sentinel used within Edgy's internal processing,
    particularly during serialization, deserialization, or data transformation.
    When caught, it indicates that a specific value or field should be
    omitted from the final output or processing, rather than representing
    an actual error condition. It inherits from `BaseException` to allow
    it to be caught by more general exception handlers if needed, though
    it's intended for specific internal handling.
    """

    ...
