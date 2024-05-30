from typing import TYPE_CHECKING, Any, Sequence, TypeVar

import sqlalchemy

from edgy.core.db.fields.base import BaseField, BaseForeignKey
from edgy.core.db.fields.core import ForeignKeyFieldFactory
from edgy.core.terminal import Print

if TYPE_CHECKING:
    from edgy import Model

T = TypeVar("T", bound="Model")

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
        **kwargs: Any,
    ) -> BaseField:
        return super().__new__(cls, to=to, **kwargs)


OneToOne = OneToOneField
