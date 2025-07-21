from inspect import isclass
from typing import Any, TypeGuard, TypeVar, get_origin

# Define a TypeVar constrained to be a type (a class).
T = TypeVar("T", bound=type)


def is_class_and_subclass(value: Any, _type: T | tuple[T, ...]) -> TypeGuard[T]:
    """
    Checks if a given `value` is both a class and a subclass of a specified `_type` (or types).

    This utility function is useful for type-safe checks in scenarios where you
    need to verify if an object is a class and adheres to a particular inheritance
    hierarchy, especially when dealing with generic types or type aliases.

    It handles cases where `value` might be a generic alias (like `typing.List[str]`)
    by inspecting its `origin` (e.g., `list` for `typing.List[str]`).

    Parameters:
        value (Any): The value to check. This could be a class, an instance,
                     a generic type, or any other Python object.
        _type (T | tuple[T, ...]): The target class (or a tuple of classes)
                                   against which `value`'s subclass relationship
                                   will be checked.

    Returns:
        TypeGuard[T]: `True` if `value` is a class and a subclass of `_type` (or any of the types in `_type`),
                      `False` otherwise. If `True`, type checkers will narrow the type of `value` to `T`.

    Examples:
        ```python
        from typing import List

        class MyBase: pass
        class MyClass(MyBase): pass
        class AnotherClass: pass

        assert is_class_and_subclass(MyClass, MyBase) == True
        assert is_class_and_subclass(MyClass, (MyBase, AnotherClass)) == True
        assert is_class_and_subclass(AnotherClass, MyBase) == False
        assert is_class_and_subclass(MyClass(), MyBase) == False # Not a class
        assert is_class_and_subclass(List[str], list) == True # Handles generic types
        assert is_class_and_subclass(str, object) == True
        ```
    """
    # Get the "origin" of the value. For generic types (e.g., `list[int]`), `get_origin` returns `list`.
    # For non-generic types or instances, it returns `None`.
    original = get_origin(value)

    # If `original` is None, it means `value` is not a generic type. In this case,
    # we directly check if `value` itself is a class. If it's not a class, it cannot be a subclass.
    if not original and not isclass(value):
        return False

    try:
        # If `original` exists, `value` is a generic type, so we check `original`'s subclass relationship.
        if original:
            return issubclass(original, _type)
        # If `original` is None, `value` is a direct class, so we check `value`'s subclass relationship.
        return issubclass(value, _type)
    except TypeError:
        # A TypeError can occur if `value` (or `original`) is not a type, e.g., an instance.
        # In such cases, it cannot be a subclass of a type, so we return False.
        return False
