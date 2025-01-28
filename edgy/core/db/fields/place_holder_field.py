from typing import Any

from edgy.core.db.fields.factories import FieldFactory
from edgy.core.db.fields.types import BaseFieldType


class PlaceholderField(FieldFactory):
    """Placeholder field, without db column"""

    def __new__(  # type: ignore
        cls,
        *,
        pydantic_field_type: Any = Any,
        **kwargs: Any,
    ) -> BaseFieldType:
        kwargs.setdefault("exclude", True)
        return super().__new__(cls, pydantic_field_type=pydantic_field_type, **kwargs)

    def clean(
        self,
        name: str,
        value: Any,
        for_query: bool = False,
    ) -> dict[str, Any]:
        return {}

    @classmethod
    def get_pydantic_type(cls, kwargs: dict[str, Any]) -> Any:
        """Returns the type for pydantic"""
        return kwargs.pop("pydantic_field_type")
