from typing import TYPE_CHECKING, Any, Sequence, TypeVar, Union

import sqlalchemy

from edgy.core.db.fields.foreign_keys import BaseForeignKeyField, ForeignKey
from edgy.core.terminal import Print

if TYPE_CHECKING:
    from edgy import Model
    from edgy.core.db.fields.base import BaseField

T = TypeVar("T", bound="Model")

terminal = Print()


class BaseOneToOneKeyField(BaseForeignKeyField):
    def __init__(
        self,
        **kwargs: Any,
    ) -> None:
        # we don't want an index here because UniqueConstraint creates already an index
        kwargs["index"] = False
        super().__init__(**kwargs)

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

    def __new__(  # type: ignore
        cls,
        to: Union["Model", str],
        *,
        index: bool=False,
        **kwargs: Any,
    ) -> "BaseField":
        if index:
            terminal.write_warning("Declaring index on a OneToOneField has no effect.")

        return super().__new__(cls, to=to, **kwargs)

OneToOne = OneToOneField
