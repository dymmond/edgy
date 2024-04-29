from inspect import isclass
from typing import Any

from typing_extensions import get_origin


def is_class_and_subclass(value: Any, _type: Any) -> bool:
    """
    Checks if a `value` is of type class and subclass.
    by checking the origin of the value against the type being
    verified.
    """
    original = get_origin(value)
    if not original and not isclass(value):
        return False

    try:
        if original:
            return original and issubclass(original, _type)
        return issubclass(value, _type)
    except TypeError:
        return False
