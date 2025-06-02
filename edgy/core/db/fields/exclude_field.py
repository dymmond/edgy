from typing import TYPE_CHECKING, Any

from pydantic.json_schema import SkipJsonSchema

from edgy.core.db.context_vars import CURRENT_PHASE
from edgy.core.db.fields.factories import FieldFactory

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType


class ExcludeField(FieldFactory, type[None]):
    """
    Meta field that masks fields
    """

    field_type: Any = Any

    def __new__(
        cls,
        **kwargs: Any,
    ) -> "BaseFieldType":
        kwargs["exclude"] = True
        kwargs["null"] = True
        kwargs["primary_key"] = False
        field = super().__new__(cls, **kwargs)
        field.metadata.append(SkipJsonSchema())

        return field

    @classmethod
    def clean(
        cls,
        obj: "BaseFieldType",
        name: str,
        value: Any,
        for_query: bool = False,
        original_fn: Any = None,
    ) -> dict[str, Any]:
        """remove any value from input."""
        return {}

    @classmethod
    def to_model(
        cls,
        obj: "BaseFieldType",
        name: str,
        value: Any,
        original_fn: Any = None,
    ) -> dict[str, Any]:
        """remove any value from input and raise when setting an attribute."""
        phase = CURRENT_PHASE.get()
        if phase == "set":
            raise ValueError("field is excluded")
        return {}

    @classmethod
    def __get__(
        cls,
        obj: "BaseFieldType",
        instance: "BaseModelType",
        owner: Any = None,
        original_fn: Any = None,
    ) -> None:
        raise ValueError("field is excluded")
