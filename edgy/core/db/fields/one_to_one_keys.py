from typing import TYPE_CHECKING, Any, Optional, Sequence, TypeVar

import sqlalchemy

from edgy.core.db.constants import CASCADE, RESTRICT, SET_NULL
from edgy.core.db.fields.base import BaseField, BaseForeignKey
from edgy.core.db.fields.core import ForeignKeyFieldFactory
from edgy.core.terminal import Print
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    from edgy import Model

T = TypeVar("T", bound="Model")


CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]
terminal = Print()


class BaseOneToOneKeyField(BaseForeignKey):
    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        target = self.target
        to_field = target.fields[target.pknames[0]]

        column_type = to_field.column_type
        constraints = [
            sqlalchemy.schema.ForeignKey(f"{target.meta.tablename}.{target.pknames[0]}", ondelete=self.on_delete)
        ]
        return [
            sqlalchemy.Column(
                name,
                column_type,
                *constraints,
                nullable=self.null,
                unique=True,
            )
        ]


class OneToOneField(ForeignKeyFieldFactory):
    """
    Representation of a one to one field.
    """

    _bases = (BaseOneToOneKeyField,)

    _type: Any = Any

    def __new__(  # type: ignore
        cls,
        to: "Model",
        *,
        null: bool = False,
        on_update: Optional[str] = CASCADE,
        on_delete: Optional[str] = RESTRICT,
        related_name: Optional[str] = None,
        **kwargs: Any,
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }

        return super().__new__(cls, **kwargs)

    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        on_delete = kwargs.get("on_delete", None)
        on_update = kwargs.get("on_update", None)
        null = kwargs.get("null")

        if on_delete is None:
            raise FieldDefinitionError("on_delete must not be null")

        if on_delete == SET_NULL and not null:
            raise FieldDefinitionError("When SET_NULL is enabled, null must be True.")

        if on_update and (on_update == SET_NULL and not null):
            raise FieldDefinitionError("When SET_NULL is enabled, null must be True.")


OneToOne = OneToOneField
