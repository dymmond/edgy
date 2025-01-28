from typing import Any

import sqlalchemy
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.mutable import MutableList

from edgy.core.db.fields.factories import FieldFactory
from edgy.core.db.fields.types import BaseFieldType
from edgy.exceptions import FieldDefinitionError

CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


class PGArrayField(FieldFactory, list):
    """PGA"""

    field_type = list

    def __new__(  # type: ignore
        cls,
        item_type: "sqlalchemy.types.TypeEngine",
        **kwargs: Any,
    ) -> BaseFieldType:
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }

        return super().__new__(cls, **kwargs)

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        item_type = kwargs.get("item_type")
        if item_type is None:
            raise FieldDefinitionError(detail=f"'item_type' is required for {cls.__name__}.")
        if not isinstance(item_type, sqlalchemy.types.TypeEngine):
            raise FieldDefinitionError(
                detail=f"'item_type' is not a sqlalchemy type ({item_type!r})."
            )

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        return MutableList.as_mutable(postgresql.ARRAY(kwargs["item_type"]))
