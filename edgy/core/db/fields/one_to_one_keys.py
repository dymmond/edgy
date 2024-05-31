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
    def get_global_constraints(
        self, name: str, columns: Sequence[sqlalchemy.Column]
    ) -> Sequence[sqlalchemy.Constraint]:
        return [
            *super().get_global_constraints(name, columns),
            sqlalchemy.UniqueConstraint(*columns),
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
