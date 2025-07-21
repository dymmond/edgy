from typing import Any

from edgy.core.db.fields.factories import FieldFactory
from edgy.core.db.fields.types import BaseFieldType


class PlaceholderField(FieldFactory):
    """
    A placeholder field that does not correspond to a database column.

    This field type is useful for model attributes that are part of the
    Pydantic validation schema but are not directly persisted to the database.
    By default, it is excluded from database operations.
    """

    def __new__(
        cls,
        *,
        pydantic_field_type: Any = Any,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Creates a new `PlaceholderField` instance.

        By default, this field is set to be excluded from database operations.

        Args:
            pydantic_field_type (Any): The Pydantic type to be used for this field.
                                       Defaults to `Any`.
            **kwargs (Any): Arbitrary keyword arguments passed to the `FieldFactory`.

        Returns:
            BaseFieldType: The constructed `PlaceholderField` instance.
        """
        # Ensure the field is excluded from database operations by default.
        kwargs.setdefault("exclude", True)
        return super().__new__(cls, pydantic_field_type=pydantic_field_type, **kwargs)

    def clean(
        self,
        name: str,
        value: Any,
        for_query: bool = False,
    ) -> dict[str, Any]:
        """
        Cleans the value for the placeholder field.

        As this field does not have a corresponding database column,
        this method always returns an empty dictionary, indicating no
        database value needs to be handled.
        """
        return {}

    @classmethod
    def get_pydantic_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the Pydantic type for the field.

        This method extracts the `pydantic_field_type` from the `kwargs`
        and uses it as the Pydantic validation type.
        """
        return kwargs.pop("pydantic_field_type")
