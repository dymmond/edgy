from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from pydantic_core import PydanticUndefined

if TYPE_CHECKING:
    from pydantic import ConfigDict

    from edgy.core.db.models import Model
    from edgy.core.db.models.metaclasses import MetaInfo
    from edgy.core.db.models.types import BaseModelType


def create_edgy_model(
    __name__: str,
    __module__: str,
    __definitions__: dict[str, Any] | None = None,
    __metadata__: MetaInfo | None = None,
    __qualname__: str | None = None,
    __config__: ConfigDict | None = None,
    __bases__: tuple[type[BaseModelType], ...] | None = None,
    __proxy__: bool = False,
    __pydantic_extra__: Any = None,
    __type_kwargs__: dict[str, Any] | None = None,
) -> type[Model]:
    """
    Generates a dynamic `edgy.Model` class with specified definitions and metadata.

    This factory function allows for the programmatic creation of Edgy model classes.
    It takes various parameters to define the model's name, module, base classes,
    field definitions, metadata, Pydantic configuration, and other advanced
    Pydantic-related arguments. This is particularly useful for creating
    temporary models, proxy models, or models with dynamic schemas.

    Parameters:
        __name__ (str): The name of the new model class. This will be the
                        class's `__name__` attribute.
        __module__ (str): The module string where the model is considered to be defined.
                          This will be the class's `__module__` attribute.
        __definitions__ (dict[str, Any] | None, optional): A dictionary of attributes
            and methods to be included in the new model class. This can include
            field definitions, custom methods, etc. Defaults to `None`.
        __metadata__ (MetaInfo | None, optional): An instance of `MetaInfo`
                                                  containing Edgy-specific metadata
                                                  for the model (e.g., table name,
                                                  registry). Defaults to `None`.
        __qualname__ (str | None, optional): The fully qualified name for the class.
                                             If `None`, it defaults to `__name__`.
        __config__ (ConfigDict | None, optional): A Pydantic `ConfigDict` to
                                                  apply to the model, influencing
                                                  Pydantic's behavior (e.g., `extra='allow'`).
                                                  Defaults to `None`.
        __bases__ (tuple[type[BaseModelType], ...] | None, optional): A tuple of base classes
                                                                      from which the new model
                                                                      will inherit. If `None`,
                                                                      it defaults to `(Model,)`.
        __proxy__ (bool, optional): A flag indicating if this model is a proxy model.
                                    Proxy models often behave differently in terms of
                                    database interactions. Defaults to `False`.
        __pydantic_extra__ (Any, optional): Extra attributes or definitions to be passed
                                            directly to Pydantic's model creation,
                                            often used for advanced Pydantic features.
                                            Defaults to `None`.
        __type_kwargs__ (dict[str, Any] | None, optional): Additional keyword arguments
                                                           to pass directly to the `type()`
                                                           constructor when creating the
                                                           class. This allows for
                                                           highly customized class creation.
                                                           Defaults to `None`.

    Returns:
        type[Model]: The newly created Edgy Model class.
    """
    # Import Model dynamically to avoid circular dependencies.
    from edgy.core.db.models.model import Model

    # Set default bases if none are provided.
    if not __bases__:
        __bases__ = (Model,)

    # Determine the qualified name, defaulting to __name__.
    qualname = __qualname__ or __name__
    # Initialize a dictionary for core class definitions.
    core_definitions: dict[str, Any] = {
        "__module__": __module__,
        "__qualname__": qualname,
        "__is_proxy_model__": __proxy__,
    }
    # Update core definitions with any provided __definitions__.
    if not __definitions__:
        __definitions__ = {}
    core_definitions.update(**__definitions__)

    # Add Pydantic config if provided.
    if __config__:
        core_definitions.update(**{"model_config": __config__})
    # Add Edgy MetaInfo if provided.
    if __metadata__:
        core_definitions.update(**{"Meta": __metadata__})
    # Add Pydantic extra definitions if provided.
    if __pydantic_extra__:
        core_definitions.update(**{"__pydantic_extra__": __pydantic_extra__})
    # Initialize type_kwargs if none are provided.
    if not __type_kwargs__:
        __type_kwargs__ = {}

    # Create the new model type dynamically using the `type` constructor.
    model: type[Model] = type(__name__, __bases__, core_definitions, **__type_kwargs__)
    return model


def generify_model_fields(model: type[BaseModelType]) -> dict[str, Any]:
    """
    Transforms the fields of a given Edgy model into a generic, unconstrained state.

    When a partial model is generated or used, it's often necessary to remove
    specific constraints, metadata, and default values from its fields to allow
    for more flexible data processing. This function iterates through all
    `model_fields` of the provided `model` and makes them generic by:
    1.  Setting their annotation to `typing.Any`, effectively removing type checks.
    2.  Setting `null` to `True` for Edgy-specific fields, making them nullable.
    3.  Setting the default value to `None` if it was previously `PydanticUndefined`,
        ensuring fields are not considered required.
    4.  Clearing all associated metadata, removing any custom validations or configurations.

    This process results in a "clean slate" version of the fields, suitable for
    internal dynamic data handling without triggering strict model validations.

    Parameters:
        model (type[BaseModelType]): The Edgy model class whose fields are to be generified.

    Returns:
        dict[str, Any]: A dictionary where keys are field names and values are the
                        modified, generic field instances. Note that the original
                        `model.model_fields` are modified in place due to direct
                        attribute assignments on the field objects.
    """
    fields: dict[str, Any] = {}

    # Iterate through each field in the model's model_fields.
    for name, field in model.model_fields.items():
        # Set the annotation of the field to Any, making it accept any type.
        field.annotation = Any
        # Attempt to set 'null' to True for Edgy-specific fields.
        # contextlib.suppress prevents AttributeError if 'null' is not an attribute (e.g., Pydantic FieldInfo).
        with contextlib.suppress(AttributeError):
            field.null = True
        # If the field's default value is PydanticUndefined (meaning it's required),
        # set it to None. This makes the field optional.
        if field.default is PydanticUndefined:
            field.default = None
        # Clear any metadata associated with the field, removing custom validations.
        field.metadata = []
        # Add the modified field to the 'fields' dictionary.
        fields[name] = field
    return fields
