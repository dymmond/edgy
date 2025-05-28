from collections.abc import Callable
from functools import cached_property
from typing import TYPE_CHECKING, Any, cast

from edgy.core.db.fields.base import BaseField
from edgy.core.db.fields.types import BaseFieldType

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType


class ComputedField(BaseField):
    def __init__(
        self,
        getter: Callable[[BaseFieldType, "BaseModelType", type["BaseModelType"] | None], Any]
        | str,
        setter: Callable[[BaseFieldType, "BaseModelType", Any], None] | str | None = None,
        fallback_getter: Callable[
            [BaseFieldType, "BaseModelType", type["BaseModelType"] | None], Any
        ]
        | None = None,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("exclude", True)
        kwargs["null"] = True
        kwargs["primary_key"] = False
        kwargs["field_type"] = kwargs["annotation"] = Any
        self.getter = getter
        self.fallback_getter = fallback_getter
        self.setter = setter
        super().__init__(
            **kwargs,
        )

    @cached_property
    def compute_getter(
        self,
    ) -> Callable[[BaseFieldType, "BaseModelType", type["BaseModelType"] | None], Any]:
        if isinstance(self.getter, str):
            fn = cast(
                Callable[[BaseFieldType, "BaseModelType", type["BaseModelType"] | None], Any]
                | None,
                getattr(self.owner, self.getter, None),
            )
        else:
            fn = self.getter
        if fn is None and self.fallback_getter is not None:
            fn = self.fallback_getter
        if fn is None:
            raise ValueError(f"No getter found for attribute: {self.getter}.")
        return fn

    @cached_property
    def compute_setter(self) -> Callable[[BaseFieldType, "BaseModelType", Any], None]:
        if isinstance(self.setter, str):
            fn = cast(
                Callable[[BaseFieldType, "BaseModelType", Any], None] | None,
                getattr(self.owner, self.setter, None),
            )
        else:
            fn = self.setter
        if fn is None:
            return lambda instance, name, value: None
        return fn

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        return {}

    def clean(
        self,
        name: str,
        value: Any,
        for_query: bool = False,
    ) -> dict[str, Any]:
        return {}

    def __get__(self, instance: "BaseModelType", owner: Any = None) -> Any:
        return self.compute_getter(self, instance, owner)

    def __set__(self, instance: "BaseModelType", value: Any) -> None:
        self.compute_setter(self, instance, value)
