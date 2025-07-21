from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast

from lilya.context import session
from pydantic.json_schema import GenerateJsonSchema, NoDefault
from pydantic_core import core_schema

import edgy

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model


class CallableDefaultJsonSchema(GenerateJsonSchema):
    """
    A custom JSON schema generator that resolves callable default values.

    When `include_callable_defaults` is True, this generator will execute
    callable default values of Pydantic fields and include their result
    in the generated schema.
    """

    def get_default_value(self, schema: core_schema.WithDefaultSchema) -> Any:
        """
        Retrieves the default value for a schema field.

        If the default value is a callable, it is executed to get the actual value.

        Args:
            schema (core_schema.WithDefaultSchema): The Pydantic core schema for the field.

        Returns:
            Any: The resolved default value.
        """
        value = super().get_default_value(schema)
        if callable(value):
            # If the default value is a callable, execute it.
            value = value()
        return value


class NoCallableDefaultJsonSchema(GenerateJsonSchema):
    """
    A custom JSON schema generator that excludes callable default values.

    When `include_callable_defaults` is False, this generator will replace
    callable default values with `NoDefault` in the generated schema,
    effectively omitting them.
    """

    def get_default_value(self, schema: core_schema.WithDefaultSchema) -> Any:
        """
        Retrieves the default value for a schema field.

        If the default value is a callable, it is replaced with `NoDefault`.

        Args:
            schema (core_schema.WithDefaultSchema): The Pydantic core schema for the field.

        Returns:
            Any: The default value, with callables replaced by `NoDefault`.
        """
        value = super().get_default_value(schema)
        if callable(value):
            # If the default value is a callable, replace it with NoDefault.
            value = NoDefault
        return value


def get_registered_models() -> dict[str, type[Model]]:
    """
    Retrieves a dictionary of all Edgy models registered for the admin interface.

    Returns:
        dict[str, type[Model]]: A dictionary where keys are model names (strings)
                                and values are the corresponding Edgy model classes.
    """
    # Access the Edgy registry instance.
    registry = edgy.monkay.instance.registry
    # Return a dictionary of models that are part of the admin_models set.
    return {name: registry.get_model(name) for name in registry.admin_models}


def get_model(model_name: str, *, no_check_admin_models: bool = False) -> type[Model]:
    """
    Retrieves a specific Edgy model by its name from the registry.

    Args:
        model_name (str): The name of the model to retrieve.
        no_check_admin_models (bool, optional): If `True`, bypasses the check
                                                to ensure the model is registered
                                                for the admin interface. Defaults to `False`.

    Returns:
        type[Model]: The Edgy model class.

    Raises:
        LookupError: If the model is not found or not registered for admin
                     (unless `no_check_admin_models` is `True`).
    """
    registry = edgy.monkay.instance.registry
    # If not bypassing admin model check, verify if the model is in admin_models.
    if not no_check_admin_models and model_name not in registry.admin_models:
        raise LookupError()
    # Retrieve the model, excluding models from the "pattern_models" type.
    return cast("type[Model]", registry.get_model(model_name, exclude={"pattern_models"}))


def get_model_json_schema(
    model: str | type[Model],
    /,
    mode: Literal["validation", "serialization"] = "validation",
    phase: str = "view",
    include_callable_defaults: bool = False,
    no_check_admin_models: bool = False,
    **kwargs: Any,
) -> dict:
    """
    Generates the JSON schema for an Edgy model.

    This function leverages the model's admin marshall class to produce a schema
    that is tailored for different phases (e.g., "view", "edit", "create") and
    can optionally include or exclude callable default values.

    Args:
        model (str | type[Model]): The model class or its name to generate the schema for.
        mode (Literal["validation", "serialization"], optional): The mode for schema
                                                                 generation ("validation" or "serialization").
                                                                 Defaults to "validation".
        phase (str, optional): The phase of the admin operation (e.g., "view", "edit", "create").
                               This influences which fields are included in the schema.
                               Defaults to "view".
        include_callable_defaults (bool, optional): If `True`, callable default values
                                                    will be executed and their results
                                                    included in the schema. Defaults to `False`.
        no_check_admin_models (bool, optional): If `True`, bypasses the check to ensure
                                                the model is registered for the admin interface.
                                                Defaults to `False`.
        **kwargs (Any): Additional keyword arguments to pass to `model_json_schema`.

    Returns:
        dict: The generated JSON schema as a dictionary.
    """
    # If a model name string is provided, retrieve the actual model class.
    if isinstance(model, str):
        model = get_model(model, no_check_admin_models=no_check_admin_models)
    # Get the appropriate admin marshall class for the specified phase.
    marshall_class = model.get_admin_marshall_class(phase=phase, for_schema=True)

    # Determine which schema generator to use based on `include_callable_defaults`.
    schema_generator = (
        CallableDefaultJsonSchema if include_callable_defaults else NoCallableDefaultJsonSchema
    )
    # Generate and return the JSON schema.
    return marshall_class.model_json_schema(
        schema_generator=schema_generator,
        mode=mode,
        **kwargs,
    )


def add_to_recent_models(model: type[Model]) -> None:
    """
    Adds a model's name to a list of recently viewed models stored in the session.

    This list is typically used to display a "recent models" section in the admin dashboard.
    It maintains a maximum of 10 unique recent models, with the most recent at the top.

    Args:
        model (type[Model]): The Edgy model class to add to the recent models list.
    """
    # If the model has no registry, it cannot be tracked, so return.
    if not model.meta.registry:
        return

    # Initialize recent_models list from session or as empty.
    if hasattr(session, "recent_models"):
        # Filter out the current model's name if it already exists to avoid duplicates
        # and limit the list to the top 10.
        recent_models = [name for name in session.recent_models[:10] if name != model.__name__]
    else:
        recent_models = []

    # Insert the current model's name at the beginning of the list.
    recent_models.insert(0, model.__name__)
    # Update the session.
    session.recent_models = recent_models


def get_recent_models() -> list[str]:
    """
    Retrieves the list of recently viewed model names from the session.

    Returns:
        list[str]: A list of strings, where each string is the name of a recently
                   viewed model. Returns an empty list if no recent models are stored.
    """
    # If 'recent_models' attribute is not present or is None in the session, return an empty list.
    if not getattr(session, "recent_models", None):
        return []
    # Cast and return the list of recent models.
    return cast(list[str], session.recent_models)
