
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Type,
    Union,
)

from edgy.core.db.fields.base import BaseField
from edgy.core.db.fields.factories import FieldFactory

if TYPE_CHECKING:
    from edgy import Model, ReflectModel


class ConcreteExcludeField(BaseField):
    def __init__(self, **kwargs: Any):
        kwargs["exclude"] = True
        kwargs["null"] = True
        kwargs["primary_key"] = False
        return super().__init__(
            **kwargs,
        )

    def clean(self, name: str, value: Any, for_query: bool = False) -> Dict[str, Any]:
        """remove any value from input"""
        return {}

    def to_model(self, name: str, value: Any, phase: str = "") -> Dict[str, Any]:
        """remove any value from input and raise when setting an attribute"""
        if phase == "set":
            raise AttributeError("field is excluded")
        return {}

    def __get__(self, instance: Union["Model", "ReflectModel"], owner: Any = None) -> None:
        raise AttributeError("field is excluded")


class ExcludeField(FieldFactory, Type[None]):
    """
    Meta field that masks fields
    """

    _bases = (ConcreteExcludeField,)
    _type: Any = Any
