from __future__ import annotations

from typing import Any

from edgy import Model


def get_model_schema(model: type[Model]) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []

    for field in model.meta.fields.values():
        fields.append(
            {
                "name": field.name,
                "type": field.__class__.__name__.lower(),
                "required": not field.null,
                "primary_key": getattr(field, "primary_key", False),
                "default": field.default if field.has_default else None,
            }
        )

    return {
        "name": model.__name__,
        "fields": fields,
    }
