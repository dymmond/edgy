from __future__ import annotations

from edgy import Model

__registered_models__: dict[str, type[Model]] = {}

__all__ = ["register_model", "get_registered_models"]


def register_model(model: type[Model]) -> None:
    name = model.__name__.lower()
    if name not in __registered_models__:
        __registered_models__[name] = model


def get_registered_models() -> dict[str, type[Model]]:
    return __registered_models__
