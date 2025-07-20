from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, TypedDict, Union

if TYPE_CHECKING:
    from faker import Faker

    from edgy.core.db.fields.types import BaseFieldType

    from .fields import FactoryField


class _ModelFactoryContext(TypedDict):
    """
    Defines the shape of the dictionary part of the ModelFactoryContext.

    This TypedDict specifies the core components that are managed within the
    factory's context, such as the Faker instance, exclusion settings,
    recursion depth, and call tracking.
    """

    faker: Faker
    """An instance of the Faker library for generating fake data."""
    exclude_autoincrement: bool
    """A boolean indicating whether autoincrementing fields should be excluded."""
    depth: int
    """The current recursion depth, used to prevent infinite loops in nested factories."""
    callcounts: dict[int, int]
    """A dictionary tracking the number of times each `FactoryField` has been called."""


if TYPE_CHECKING:
    # During type checking, ModelFactoryContext is a Protocol that combines
    # Faker's methods with _ModelFactoryContext's dictionary items.
    # This allows attribute-style access to Faker methods directly on the context.
    class ModelFactoryContext(Faker, _ModelFactoryContext, Protocol):
        """
        Represents the context available during model factory data generation.

        This protocol allows the context to behave both as a dictionary (for
        `faker`, `exclude_autoincrement`, `depth`, `callcounts`) and as a
        `Faker` instance (allowing direct calls to Faker methods like `context.name()`).
        This duality is achieved through `TypedDict` and `Protocol` inheritance.
        """

        pass
else:
    # At runtime, ModelFactoryContext is simply the _ModelFactoryContext TypedDict.
    # The attribute-style access to Faker methods is handled by the Broadcaster-like
    # `ModelFactoryContextImplementation` class at runtime.
    ModelFactoryContext = _ModelFactoryContext


# Type alias for a callable that generates a parameter for a FactoryField.
FactoryParameterCallback: TypeAlias = Callable[
    [
        "FactoryField",  # The FactoryField instance being processed.
        ModelFactoryContext,  # The current factory context.
        str,  # The name of the parameter being generated.
    ],
    Any,  # The generated value for the parameter.
]
"""
A callback type used to dynamically generate parameters for `FactoryField`s.
This allows parameters to be context-aware or depend on other generated values.
"""

# Type alias for a dictionary of parameters for a FactoryField.
FactoryParameters: TypeAlias = dict[str, Any | FactoryParameterCallback]
"""
A dictionary where keys are parameter names and values can be either:
-   `Any`: A direct value for the parameter.
-   `FactoryParameterCallback`: A callable that generates the parameter's value dynamically.
"""

# Type alias for the main callback function that generates a field's value.
FactoryCallback: TypeAlias = Callable[
    [
        "FactoryField",  # The FactoryField instance requesting a value.
        ModelFactoryContext,  # The current factory context.
        dict[
            str, Any
        ],  # Resolved parameters for the callback (after `FactoryParameters` are processed).
    ],
    Any,  # The generated value for the field.
]
"""
The core callback type responsible for generating the final value for a field.
This callback receives the `FactoryField` itself, the `ModelFactoryContext`,
and a dictionary of resolved parameters.
"""

# Type alias for specifying a field factory callback, allowing both strings (Faker method names)
# and direct callables.
FieldFactoryCallback: TypeAlias = str | FactoryCallback
"""
A union type representing how a `FactoryField`'s generation logic can be defined:
-   `str`: A string name corresponding to a Faker provider method (e.g., "name", "email").
-   `FactoryCallback`: A direct callable function for more complex generation logic.
"""

# Type alias for specifying the type of a factory field, allowing strings (type names),
# instances of BaseFieldType, or the class type of BaseFieldType.
FactoryFieldType: TypeAlias = Union[str, "BaseFieldType", type["BaseFieldType"]]
"""
Represents the type of the database field that a `FactoryField` corresponds to.
This can be specified as:
-   `str`: The string name of the field type (e.g., "CharField", "IntegerField").
-   `BaseFieldType`: An instance of an Edgy field type.
-   `type[BaseFieldType]`: The class type of an Edgy field (e.g., `edgy.fields.CharField`).
"""
