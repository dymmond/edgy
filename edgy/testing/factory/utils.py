from __future__ import annotations

from collections.abc import Callable
from inspect import isclass
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from faker import Faker

    from edgy.core.db.fields.types import BaseFieldType

    from .fields import FactoryField
    from .types import FactoryCallback, FactoryParameterCallback


EDGY_FIELD_PARAMETERS: dict[str, tuple[str, Callable[[BaseFieldType, str, Faker], Any]]] = {
    "ge": ("min", lambda field, attr_name, faker: getattr(field, attr_name)),
    "le": ("max", lambda field, attr_name, faker: getattr(field, attr_name)),
    "multiple_of": ("step", lambda field, attr_name, faker: getattr(field, attr_name)),
    "decimal_places": ("right_digits", lambda field, attr_name, faker: getattr(field, attr_name)),
}


def edgy_field_param_extractor(
    factory_fn: FactoryCallback | str,
    *,
    remapping: dict[str, tuple[str, Callable[[BaseFieldType, str, Faker], Any]] | None]
    | None = None,
    defaults: dict[str, Any | FactoryParameterCallback] | None = None,
) -> FactoryCallback:
    remapping = remapping or {}
    remapping = {**EDGY_FIELD_PARAMETERS, **remapping}
    if isinstance(factory_fn, str):
        factory_name = factory_fn
        factory_fn = lambda field, faker, kwargs: getattr(faker, factory_name)(**kwargs)  # noqa

    def mapper_fn(field: FactoryField, faker: Faker, kwargs: dict[str, Any]) -> Any:
        edgy_field = field.owner.meta.model.meta.fields[field.name]
        for attr, mapper in remapping.items():
            if mapper is None:
                continue
            if getattr(edgy_field, attr, None) is not None:
                kwargs.setdefault(mapper[0], mapper[1](edgy_field, attr, faker))
        if defaults:
            for name, value in defaults.items():
                if name not in kwargs:
                    if callable(value) and not isclass(value):
                        value = value(field, faker, name)
                    kwargs[name] = value
        return cast("FactoryCallback", factory_fn)(field, faker, kwargs)

    return mapper_fn


def default_wrapper(
    factory_fn: FactoryCallback | str,
    defaults: dict[str, Any],
) -> FactoryCallback:
    """A simplified edgy_field_param_extractor."""
    if isinstance(factory_fn, str):
        factory_name = factory_fn
        factory_fn = lambda field, faker, kwargs: getattr(faker, factory_name)(**kwargs)  # noqa

    def mapper_fn(field: FactoryField, faker: Faker, kwargs: dict[str, Any]) -> Any:
        for name, value in defaults.items():
            if name not in kwargs:
                if callable(value) and not isclass(value):
                    value = value(field, faker, name)
                kwargs[name] = value
        return factory_fn(field, faker, kwargs)

    return mapper_fn
