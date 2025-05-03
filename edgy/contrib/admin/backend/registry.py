from __future__ import annotations

from edgy import Model

# Internal registry for storing model references
__registry__: dict[str, type[Model]] = {}


def admin_register(model: type[Model]) -> None:
    """
    Register a model class to be exposed via the admin interface.
    """
    name = model.__name__.lower()
    if name in __registry__:
        raise ValueError(f"Model '{name}' is already registered.")
    __registry__[name] = model


def get_registered_models() -> dict[str, type[Model]]:
    """
    Return all registered models.
    """
    return __registry__


def get_model_by_name(name: str) -> type[Model] | None:  # noqa
    """
    Get a registered model by lowercase name.
    """
    return __registry__.get(name.lower())
