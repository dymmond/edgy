from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Type,
    Union,
)

from edgy.core.db.fields.factories import FieldFactory
from edgy.core.db.fields.types import BaseFieldType

if TYPE_CHECKING:
    from edgy import Model, ReflectModel


class ExcludeField(FieldFactory, Type[None]):
    """
    Meta field that masks fields
    """

    field_type: Any = Any

    def __new__(  # type: ignore
        cls,
        **kwargs: Any,
    ) -> BaseFieldType:
        kwargs["exclude"] = True
        kwargs["null"] = True
        kwargs["primary_key"] = False
        return super().__new__(cls, **kwargs)

    @classmethod
    def clean(
        cls,
        obj: BaseFieldType,
        name: str,
        value: Any,
        for_query: bool = False,
        original_fn: Any = None,
    ) -> Dict[str, Any]:
        """remove any value from input."""
        return {}

    @classmethod
    def to_model(
        cls,
        obj: BaseFieldType,
        name: str,
        value: Any,
        phase: str = "",
        original_fn: Any = None,
    ) -> Dict[str, Any]:
        """remove any value from input and raise when setting an attribute."""
        if phase == "set":
            raise AttributeError("field is excluded")
        return {}

    @classmethod
    def __get__(
        cls,
        obj: BaseFieldType,
        instance: Union["Model", "ReflectModel"],
        owner: Any = None,
        original_fn: Any = None,
    ) -> None:
        raise AttributeError("field is excluded")
