from typing import TYPE_CHECKING, Any, Sequence, TypeVar

import sqlalchemy

from edgy.core.db.fields.base import BaseField, BaseForeignKey
from edgy.core.db.fields.core import ForeignKeyFieldFactory
from edgy.core.terminal import Print

if TYPE_CHECKING:
    from edgy import Model

T = TypeVar("T", bound="Model")

terminal = Print()


class BaseForeignKeyField(BaseForeignKey):
    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        target = self.target
        to_field = target.fields[target.pknames[0]]

        column_type = to_field.column_type
        constraints = [
            sqlalchemy.schema.ForeignKey(
                f"{target.meta.tablename}.{target.pknames[0]}",
                ondelete=self.on_delete,
                onupdate=self.on_update,
                name=f"fk_{self.owner.meta.tablename}_{target.meta.tablename}" f"_{target.pknames[0]}_{name}",
            )
        ]
        return [sqlalchemy.Column(name, column_type, *constraints, nullable=self.null)]


class ForeignKey(ForeignKeyFieldFactory):
    _bases = (BaseForeignKeyField,)
    _type: Any = Any

    def __new__(  # type: ignore
        cls,
        to: "Model",
        **kwargs: Any,
    ) -> BaseField:
        return super().__new__(cls, to=to, **kwargs)
