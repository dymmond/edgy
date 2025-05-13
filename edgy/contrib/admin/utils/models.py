from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import edgy

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model


def get_registered_models() -> dict[str, type[Model]]:
    return edgy.monkay.instance.registry.admin_models


def get_model(model_name: str) -> type[Model]:
    return get_registered_models()[model_name]


def get_model_json_schema(
    model_name: str, mode: Literal["validation", "serialization"] = "validation"
) -> dict:
    return get_model(model_name).model_json_schema(mode=mode)
