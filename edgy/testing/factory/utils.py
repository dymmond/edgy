from __future__ import annotations

from collections.abc import Callable, Collection
from inspect import isclass
from itertools import chain
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType

    from .fields import FactoryField
    from .types import FactoryCallback, FactoryParameterCallback, ModelFactoryContext


# A dictionary mapping common Edgy field validation parameters to Faker's parameter names
# and a callback to extract the value from the Edgy field.
EDGY_FIELD_PARAMETERS: dict[
    str, tuple[str, Callable[[BaseFieldType, str, ModelFactoryContext], Any]]
] = {
    "ge": (
        "min",  # Maps 'greater than or equal to' to Faker's 'min' parameter.
        lambda field, attr_name, context: getattr(field, attr_name),
    ),
    "le": (
        "max",  # Maps 'less than or equal to' to Faker's 'max' parameter.
        lambda field, attr_name, context: getattr(field, attr_name),
    ),
    "multiple_of": (
        "step",  # Maps 'multiple_of' to Faker's 'step' parameter for numbers.
        lambda field, attr_name, context: getattr(field, attr_name),
    ),
    "decimal_places": (
        "right_digits",  # Maps 'decimal_places' to Faker's 'right_digits' for decimals/floats.
        lambda field, attr_name, context: getattr(field, attr_name),
    ),
}


def remove_unparametrized_relationship_fields(
    model: type[BaseModelType],
    kwargs: dict[str, Any],
    extra_exclude: Collection[str | Literal[False]] = (),
) -> None:
    """
    Modifies the `kwargs` dictionary to exclude relationship fields that
    are not explicitly parametrized and have default values.

    This function helps prevent unwanted recursion or redundant data generation
    for relationship fields (like `ForeignKey`, `ManyToManyField`, and
    `RefForeignKey`) when they are not explicitly specified during factory
    creation. It ensures that if a relationship field has a default and isn't
    being overridden, it's marked for exclusion in the `build_values` process.

    Parameters:
        model (type[BaseModelType]): The Edgy model class being processed.
        kwargs (dict[str, Any]): The keyword arguments dictionary being
                                 prepared for the `build_values` method.
                                 This dictionary is modified in place.
        extra_exclude (Collection[str | Literal[False]], optional):
            Additional field names to exclude. This is typically used to
            exclude specific back-references in recursive factory calls.
            Defaults to an empty tuple.
    """
    # Extract 'parameters' and 'exclude' from kwargs, providing defaults if not present.
    parameters: dict[str, dict[str, Any]] = kwargs.get("parameters") or {}
    excluded: set[str | Literal[False]] = {*(kwargs.get("exclude") or []), *extra_exclude}
    # cleanup related_name False
    # Remove any `False` literal that might be present in excluded (e.g., from Literal[False]).
    excluded.discard(False)

    # Iterate through all relationship fields (including RefForeignKeys).
    for field_name in chain(model.meta.relationship_fields, model.meta.ref_foreign_key_fields):
        field = model.meta.fields[field_name]
        # If the field is not in 'parameters' (meaning it's not being explicitly set)
        # AND it has a default value (e.g., a default value from the model or factory).
        if field_name not in parameters and field.has_default():
            excluded.add(field_name)  # Add it to the list of excluded fields.

    # Update the 'exclude' key in the kwargs with the modified set.
    kwargs["exclude"] = excluded


def edgy_field_param_extractor(
    factory_fn: FactoryCallback | str,
    *,
    remapping: dict[
        str, tuple[str, Callable[[BaseFieldType, str, ModelFactoryContext], Any]] | None
    ]
    | None = None,
    defaults: dict[str, Any | FactoryParameterCallback] | None = None,
) -> FactoryCallback:
    """
    Creates a `FactoryCallback` that extracts parameters from an Edgy model field
    and maps them to arguments for a Faker function or another `FactoryCallback`.

    This function is a powerful utility for automating the generation of data
    based on the constraints and definitions of Edgy model fields. It allows
    seamless integration of Edgy field attributes (like `max_length`, `ge`, `le`)
    with Faker's generation methods.

    Parameters:
        factory_fn (FactoryCallback | str): The primary callback function or a
            string representing a Faker method name that will generate the field's value.
        remapping (dict[str, tuple[str, Callable[[BaseFieldType, str, ModelFactoryContext], Any]] | None] | None,
        optional):
            A dictionary defining how Edgy field attributes should be remapped to
            parameters for `factory_fn`. Each entry maps an Edgy field attribute name
            (e.g., "max_length") to a tuple containing:
            1.  The corresponding parameter name for `factory_fn` (e.g., "max_nb_chars").
            2.  A callable that extracts the value from the Edgy field instance.
            Setting a remapping value to `None` explicitly disables that remapping.
            This dictionary is merged with `EDGY_FIELD_PARAMETERS`.
            Defaults to `None`.
        defaults (dict[str, Any | FactoryParameterCallback] | None, optional):
            A dictionary of default parameters to apply to `factory_fn` if
            they are not already present in the `kwargs`. Values can be direct
            data or `FactoryParameterCallback` for dynamic defaults.
            Defaults to `None`.

    Returns:
        FactoryCallback: A new callback function that first extracts and maps
                         parameters from the Edgy field, then applies defaults,
                         and finally calls the `factory_fn` with the prepared parameters.
    """
    # Merge provided remapping with global EDGY_FIELD_PARAMETERS, prioritizing provided.
    remapping = remapping or {}
    remapping = {**EDGY_FIELD_PARAMETERS, **remapping}

    # If factory_fn is a string, wrap it in a lambda to call the Faker method.
    if isinstance(factory_fn, str):
        factory_name = factory_fn
        factory_fn = lambda field, context, kwargs: getattr(context["faker"], factory_name)(  # noqa
            **kwargs
        )

    def mapper_fn(
        field: FactoryField, context: ModelFactoryContext, kwargs: dict[str, Any]
    ) -> Any:
        """
        The inner function that performs parameter extraction and calls the main factory function.
        """
        # Get the corresponding Edgy field from the owner model's meta.
        edgy_field = field.owner.meta.model.meta.fields[field.name]

        # Apply remappings: iterate through defined remappings.
        for attr, mapper in remapping.items():
            if mapper is None:  # Skip if remapping is explicitly set to None.
                continue
            # If the Edgy field has the attribute and its value is not None.
            if getattr(edgy_field, attr, None) is not None:
                # Use setdefault to ensure existing kwargs are not overwritten.
                # Call the mapper's callable to get the value.
                kwargs.setdefault(mapper[0], mapper[1](edgy_field, attr, context))

        # Apply additional defaults if provided.
        if defaults:
            for name, value in defaults.items():
                if name not in kwargs:  # Only set default if parameter not already present.
                    # If the default value is a callable (and not a class), execute it.
                    if callable(value) and not isclass(value):
                        value = value(field, context, name)
                    kwargs[name] = value

        # Finally, call the original factory_fn with the prepared keyword arguments.
        return factory_fn(field, context, kwargs)

    return mapper_fn


def default_wrapper(
    factory_fn: FactoryCallback | str,
    defaults: dict[str, Any],
) -> FactoryCallback:
    """
    A simplified `edgy_field_param_extractor` that only applies a fixed set of default parameters.

    This utility is useful when a Faker function requires specific default arguments
    that are not derived from Edgy field attributes but should always be applied
    unless explicitly overridden.

    Parameters:
        factory_fn (FactoryCallback | str): The primary callback function or a
            string representing a Faker method name that will generate the field's value.
        defaults (dict[str, Any]): A dictionary of default parameters to apply
                                   to `factory_fn` if they are not already present
                                   in the `kwargs`. Values can be direct data or
                                   callable for dynamic defaults.

    Returns:
        FactoryCallback: A new callback function that applies the given defaults
                         and then calls the `factory_fn`.
    """
    # If factory_fn is a string, wrap it in a lambda to call the Faker method.
    if isinstance(factory_fn, str):
        factory_name = factory_fn
        # Simplified lambda signature for faker, assumes context['faker']
        factory_fn = lambda field, context, kwargs: getattr(context["faker"], factory_name)(  # noqa
            **kwargs
        )

    def mapper_fn(
        field: FactoryField, context: ModelFactoryContext, kwargs: dict[str, Any]
    ) -> Any:
        """
        The inner function that applies defaults and calls the main factory function.
        """
        for name, value in defaults.items():
            if name not in kwargs:  # Only set default if parameter not already present.
                # If the default value is a callable (and not a class), execute it.
                if callable(value) and not isclass(value):
                    value = value(field, context, name)
                kwargs[name] = value
        # Call the original factory_fn with the prepared keyword arguments.
        return factory_fn(field, context, kwargs)

    return mapper_fn
