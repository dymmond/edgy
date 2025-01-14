from __future__ import annotations

from inspect import isclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from faker import Faker

    from .base import ModelFactory
    from .types import FactoryCallback, FactoryFieldType, FactoryParameters


class FactoryField:
    owner: ModelFactory

    def __init__(
        self,
        *,
        exclude: bool = False,
        callback: FactoryCallback | None = None,
        parameters: FactoryParameters | None = None,
        field_type: FactoryFieldType | None = None,
        name: str = "",
        no_copy: bool = False,
    ) -> None:
        self.exclude = exclude
        self.no_copy = no_copy
        self.name = name
        self.parameters = parameters or {}
        self.callback = callback
        if field_type:
            if not isclass(field_type):
                field_type = type(field_type)
            if not isinstance(field_type, str):
                field_type = field_type.__name__
        else:
            field_type = None
        self.field_type: str | None = field_type

    def __copy__(self) -> FactoryField:
        _copy = FactoryField(
            exclude=self.exclude,
            no_copy=self.no_copy,
            callback=self.callback,
            parameters=self.parameters.copy(),
            field_type=self.field_type,
            name=self.name,
        )
        _copy.owner = self.owner
        return _copy

    def __call__(self, *, faker: Faker, parameters: FactoryParameters | None = None) -> Any:
        current_parameters: FactoryParameters = {}
        if self.parameters:
            current_parameters.update(self.parameters)
        if parameters:
            current_parameters.update(parameters)
        if self.callback:
            return self.callback(self.owner, faker, current_parameters)
        else:
            return self.owner.meta.mappings[self.field_type](self.owner, faker, current_parameters)


__all__ = ["FactoryField"]
