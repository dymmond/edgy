from __future__ import annotations

from typing import Any

import sqlalchemy
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.mutable import MutableList

from edgy.core.db.fields.factories import FieldFactory
from edgy.core.db.fields.types import BaseFieldType
from edgy.exceptions import FieldDefinitionError


class PGArrayField(FieldFactory, list):
    """
    PostgreSQL-specific Array Field for Edgy models.

    This field allows storing Python lists directly in a PostgreSQL ARRAY column.
    It leverages SQLAlchemy's `postgresql.ARRAY` type and `MutableList`
    to ensure that changes to the Python list are detected and persisted to the database.

    Attributes:
        field_type (list): The Python type representing the field (always `list`).
    """

    field_type = list

    def __new__(
        cls,
        item_type: sqlalchemy.types.TypeEngine,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Creates a new `PGArrayField` instance.

        Args:
            item_type (sqlalchemy.types.TypeEngine): The SQLAlchemy type of the
                                                      elements within the array (e.g., `sqlalchemy.Integer`).
            **kwargs (Any): Arbitrary keyword arguments passed to the `FieldFactory`.

        Returns:
            BaseFieldType: The constructed `PGArrayField` instance.
        """
        # Pass the `item_type` to the base `FieldFactory` for later use in `get_column_type`.
        return super().__new__(cls, item_type=item_type, **kwargs)

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Validates the parameters for a `PGArrayField`.

        Ensures that `item_type` is provided and is a valid SQLAlchemy type engine.

        Args:
            kwargs (dict[str, Any]): The dictionary of keyword arguments passed
                                     during field construction.

        Raises:
            FieldDefinitionError: If `item_type` is missing or not a SQLAlchemy type.
        """
        item_type = kwargs.get("item_type")
        if item_type is None:
            raise FieldDefinitionError(detail=f"'item_type' is required for {cls.__name__}.")
        if not isinstance(item_type, sqlalchemy.types.TypeEngine):
            raise FieldDefinitionError(
                detail=f"'item_type' is not a sqlalchemy type ({item_type!r})."
            )

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the SQLAlchemy column type for the `PGArrayField`.

        It wraps the `postgresql.ARRAY` type with `MutableList.as_mutable` to enable
        detection of in-place list modifications (e.g., `append()`, `pop()`).

        Args:
            kwargs (dict[str, Any]): The keyword arguments provided during field initialization,
                                     which must contain `item_type`.

        Returns:
            Any: A `MutableList` wrapped `postgresql.ARRAY` SQLAlchemy type.
        """
        # Create a PostgreSQL array column type with the specified item_type.
        # Wrap it with MutableList.as_mutable to enable tracking of in-place
        # mutations on Python lists, ensuring changes are propagated to the DB.
        return MutableList.as_mutable(postgresql.ARRAY(kwargs["item_type"]))
