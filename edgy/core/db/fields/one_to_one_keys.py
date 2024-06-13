from typing import TYPE_CHECKING, Sequence, TypeVar

import sqlalchemy

from edgy.core.db.fields.foreign_keys import BaseForeignKeyField, ForeignKey
from edgy.core.terminal import Print

if TYPE_CHECKING:
    from edgy import Model

T = TypeVar("T", bound="Model")

terminal = Print()


class BaseOneToOneKeyField(BaseForeignKeyField):
    def get_global_constraints(
        self, name: str, columns: Sequence[sqlalchemy.Column]
    ) -> Sequence[sqlalchemy.Constraint]:
        return [
            *super().get_global_constraints(name, columns),
            sqlalchemy.UniqueConstraint(*columns),
        ]


class OneToOneField(ForeignKey):
    """
    Representation of a one to one field.
    """

    _bases = (BaseOneToOneKeyField,)


OneToOne = OneToOneField
