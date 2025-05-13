from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

import edgy

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model


def get_registered_models() -> dict[str, type[Model]]:
    registry = edgy.monkay.instance.registry
    return {name: registry.get_model(name) for name in registry.admin_models}


def get_model(model_name: str) -> type[Model]:
    registry = edgy.monkay.instance.registry
    if model_name not in registry.admin_models:
        raise LookupError()
    return cast("type[Model]", registry.get_model(model_name, exclude={"pattern_models"}))


def get_model_json_schema(
    model_name: str, mode: Literal["validation", "serialization"] = "validation"
) -> dict:
    return get_model(model_name).model_json_schema(mode=mode)
