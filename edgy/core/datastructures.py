from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HashableBaseModel(BaseModel):
    """
    A Pydantic BaseModel extension designed to provide consistent hashing behavior,
    especially for models containing mutable types like lists and sets.

    Pydantic's default `BaseModel` does not automatically make instances hashable
    in a way that accounts for mutable attributes, which can lead to issues when
    instances are used in sets or as dictionary keys. This class addresses this
    by customising the `__hash__` method. It converts mutable attributes (lists
    and sets) into immutable tuples before computing the hash, ensuring that
    the hash value remains consistent as long as the model's content (after
    this conversion) does not change.

    Attributes:
        __slots__: Used to conserve memory by preventing the creation of instance
                   dictionaries, and allowing weak references to instances.
    """

    __slots__ = ["__weakref__"]

    def __hash__(self) -> Any:
        """
        Computes a hash value for the model instance.

        This method iterates through the model's attributes, converting lists
        and sets to tuples to ensure hashability, and then combines these
        values with the model's type to produce a consistent hash.

        Returns:
            Any: An integer hash value for the model instance.
        """
        values: Any = {}
        # Iterate over the instance's dictionary to access its attributes.
        for key, value in self.__dict__.items():
            values[key] = None  # Initialize to None before assignment
            # If the value is a list or a set, convert it to a tuple for hashability.
            if isinstance(value, list | set):
                values[key] = tuple(value)
            else:
                # Otherwise, use the value directly.
                values[key] = value
        # Compute the hash based on the type of the model and a tuple of its
        # processed attribute values. The tuple conversion ensures the order
        # of attributes does not affect the hash if they are consistently added.
        return hash((type(self),) + tuple(values))


class ArbitraryHashableBaseModel(HashableBaseModel):
    """
    Extends `HashableBaseModel` to allow arbitrary types and extra fields in the model.

    This model inherits the custom hashing logic from `HashableBaseModel` and
    configures Pydantic to permit:
    * Arbitrary types: Fields can be of any Python type, not just Pydantic-compatible ones.
    * Extra fields: Additional fields not explicitly defined in the model schema
        are allowed when data is loaded.
    """

    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}
