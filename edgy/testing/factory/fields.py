from __future__ import annotations

from inspect import isclass
from typing import TYPE_CHECKING, Any, cast

from .context_vars import model_factory_context

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.metaclasses import MetaInfo as ModelMetaInfo

    from .base import ModelFactory
    from .types import (
        FactoryCallback,
        FactoryFieldType,
        FactoryParameters,
        FieldFactoryCallback,
        ModelFactoryContext,
    )


class FactoryField:
    owner: type[ModelFactory]
    parameters: FactoryParameters
    no_copy: bool
    original_name: str
    _field_type: str = ""
    _callback: FactoryCallback | None = None

    def __init__(
        self,
        *,
        exclude: bool = False,
        callback: FieldFactoryCallback | None = None,
        parameters: FactoryParameters | None = None,
        field_type: FactoryFieldType | None = None,
        name: str = "",
        no_copy: bool = False,
    ) -> None:
        self.exclude = exclude
        self.no_copy = no_copy
        self.name = name
        self.parameters = parameters or {}
        self.field_type = field_type  # type: ignore
        if isinstance(callback, str):
            callback_name = callback
            callback = lambda field, context, parameters: getattr(context["faker"], callback_name)(  # noqa
                **parameters
            )
        self.callback = callback

    def get_field_type(self, *, db_model_meta: ModelMetaInfo | None = None) -> str:
        if self.field_type:
            return self.field_type
        elif db_model_meta is None:
            db_model_meta = self.owner.meta.model.meta
        return type(db_model_meta.fields[self.name]).__name__

    def get_callback(self) -> FactoryCallback:
        if self.callback:
            return self.callback
        elif self._callback is None:
            self._callback = self.owner.meta.mappings[self.get_field_type()]
        return self._callback

    def get_parameters(
        self,
        *,
        context: ModelFactoryContext,
        parameters: FactoryParameters | None = None,
    ) -> dict[str, Any]:
        current_parameters: FactoryParameters = {}
        for parameter_dict in [parameters or {}, self.parameters]:
            for name, parameter in parameter_dict.items():
                if name not in current_parameters:
                    if callable(parameter) and not isclass(parameter):
                        current_parameters[name] = parameter(self, context, name)
                    else:
                        current_parameters[name] = parameter
        return current_parameters

    @property
    def field_type(self) -> str:
        return self._field_type

    @field_type.setter
    def field_type(self, value: FactoryFieldType | None) -> None:
        if value:
            if not isinstance(value, str) and not isclass(value):
                value = cast(type["BaseFieldType"], type(value))
            if not isinstance(value, str):
                value = value.__name__
        self._field_type = cast(str, value or "")

    @field_type.deleter
    def field_type(self) -> None:
        self._field_type = ""

    def __copy__(self) -> FactoryField:
        _copy = FactoryField(
            exclude=self.exclude,
            no_copy=self.no_copy,
            callback=self.callback,
            parameters=self.parameters.copy(),
            name=self.name,
            field_type=self.field_type,
        )
        if hasattr(self, "owner"):
            _copy.owner = self.owner
        if hasattr(self, "original_name"):
            _copy.original_name = self.original_name
        return _copy

    def inc_callcount(self, *, amount: int = 1, callcounts: dict[int, int] | None = None) -> int:
        if callcounts is None:
            context = model_factory_context.get()
            callcounts = context["callcounts"]
        count = callcounts.setdefault(id(self), 0)
        count += amount
        callcounts[id(self)] = count
        return count

    def get_callcount(self) -> int:
        context = model_factory_context.get()
        return context["callcounts"].get(id(self), 0)

    def __call__(self, *, context: ModelFactoryContext, parameters: FactoryParameters) -> Any:
        return self.get_callback()(self, context, parameters)


__all__ = ["FactoryField"]
