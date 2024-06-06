from typing import TYPE_CHECKING, Any, TypeVar

from edgy.core.db.fields.base import BaseField, BaseForeignKey
from edgy.core.db.fields.core import ForeignKeyFieldFactory
from edgy.core.terminal import Print

if TYPE_CHECKING:
    from edgy import Model

T = TypeVar("T", bound="Model")

terminal = Print()


class BaseForeignKeyField(BaseForeignKey):
    pass


class ForeignKey(ForeignKeyFieldFactory):
    _bases = (BaseForeignKeyField,)
    _type: Any = Any

    def __new__(  # type: ignore
        cls,
        to: "Model",
        **kwargs: Any,
    ) -> BaseField:
        return super().__new__(cls, to=to, **kwargs)
