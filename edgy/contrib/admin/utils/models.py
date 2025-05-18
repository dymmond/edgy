from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic.json_schema import GenerateJsonSchema, NoDefault
from pydantic_core import core_schema

import edgy

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model


class CallableDefaultJsonSchema(GenerateJsonSchema):
    def get_default_value(self, schema: core_schema.WithDefaultSchema) -> Any:
        value = super().get_default_value(schema)
        if callable(value):
            value = value()
        return value


class NoCallableDefaultJsonSchema(GenerateJsonSchema):
    def get_default_value(self, schema: core_schema.WithDefaultSchema) -> Any:
        value = super().get_default_value(schema)
        if callable(value):
            value = NoDefault
        return value


def get_registered_models() -> dict[str, type[Model]]:
    registry = edgy.monkay.instance.registry
    return {name: registry.get_model(name) for name in registry.admin_models}


def get_model(model_name: str) -> type[Model]:
    registry = edgy.monkay.instance.registry
    if model_name not in registry.admin_models:
        raise LookupError()
    return cast("type[Model]", registry.get_model(model_name, exclude={"pattern_models"}))


def get_model_json_schema(
    model_name: str,
    mode: Literal["validation", "serialization"] = "validation",
    include_callable_defaults: bool = False,
) -> dict:
    return get_model(model_name).model_json_schema(
        schema_generator=CallableDefaultJsonSchema
        if include_callable_defaults
        else NoCallableDefaultJsonSchema,
        mode=mode,
    )
