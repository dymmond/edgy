from importlib import import_module
from typing import Any
from warnings import warn

warn(
    "This module is deprecated. Use `monkay.load` instead.",
    DeprecationWarning,
    stacklevel=2,
)


def import_string(dotted_path: str) -> Any:
    """
    Imports a module and retrieves an attribute or class specified by a dotted path.

    This function takes a string in the format "module.submodule.attribute_name"
    and attempts to import the specified module, then retrieve the attribute or
    class indicated by the last component of the path.

    Args:
        dotted_path (str): The string representing the dotted module path
            (e.g., "my_app.my_module.MyClass" or "my_app.utils.my_function").

    Returns:
        Any: The imported attribute or class.

    Raises:
        ImportError: If the `dotted_path` does not look like a module path,
            or if the module cannot be imported, or if the specified attribute/class
            is not found within the module.
    """
    try:
        # Split the dotted path into the module path and the class/attribute name.
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError as err:
        # If rsplit fails, it means the path doesn't contain a dot,
        # so it's not a valid dotted module path.
        raise ImportError(f"{dotted_path} doesn't look like a module path") from err

    # Import the module dynamically.
    module = import_module(module_path)

    try:
        # Get the attribute or class from the imported module.
        return getattr(module, class_name)
    except AttributeError as err:
        # If getattr fails, it means the module does not define the specified
        # attribute or class.
        raise ImportError(
            f'Module "{module_path}" does not define a "{class_name}" attribute/class'
        ) from err
