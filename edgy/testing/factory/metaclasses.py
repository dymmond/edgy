from __future__ import annotations

from inspect import getmro, isclass
from typing import TYPE_CHECKING, Any, Literal, cast

import monkay
from pydantic import ValidationError

from edgy.core.db.models import Model
from edgy.core.terminal import Print
from edgy.testing.exceptions import InvalidModelError
from edgy.utils.compat import is_class_and_subclass

from .fields import FactoryField
from .mappings import DEFAULT_MAPPING

if TYPE_CHECKING:
    from .base import ModelFactory
    from .types import FactoryCallback

# Initialize a terminal printer for warnings and errors.
terminal = Print()


# this is not models MetaInfo
class MetaInfo:
    """
    Stores metadata for a `ModelFactory` class.

    This class holds information essential for the factory's operation,
    including the associated Edgy model, the `Faker` instance, field
    configurations, and mappings between database field types and Faker
    generation callbacks.

    Attributes:
        model (type[Model]): The Edgy model class that this factory is
                              designed to generate instances of.
        fields (dict[str, FactoryField]): A dictionary mapping field names
                                          to their `FactoryField` configurations.
        faker (Any): An instance of the `Faker` library used for data generation.
        mappings (dict[str, FactoryCallback | None]): A dictionary mapping
                                                      Edgy database field type
                                                      names (e.g., "CharField")
                                                      to their corresponding
                                                      `FactoryCallback` functions
                                                      or `None` if no default
                                                      mapping exists.
        callcounts (dict[int, int]): A dictionary used to track call counts
                                     for `FactoryField` instances, primarily
                                     for managing recursive generation.
    """

    # Use __slots__ for memory efficiency, as these attributes are fixed.
    __slots__ = ("model", "fields", "faker", "mappings", "callcounts")
    model: type[Model]
    mappings: dict[str, FactoryCallback | None]

    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        """
        Initializes the `MetaInfo` instance.

        Parameters:
            meta (Any, optional): An existing `MetaInfo` object to copy
                                  attributes from. This is used during
                                  inheritance. Defaults to `None`.
            **kwargs (Any): Arbitrary keyword arguments to set as attributes
                            on the `MetaInfo` instance.
        """
        self.fields: dict[str, FactoryField] = {}
        self.mappings: dict[str, FactoryCallback | None] = {}
        self.callcounts: dict[int, int] = {}
        # Copy attributes from a provided `meta` object if available.
        for slot in self.__slots__:
            value = getattr(meta, slot, None)
            if value is not None:
                setattr(self, slot, value)
        # Set any additional keyword arguments as attributes.
        for name, value in kwargs.items():
            setattr(self, name, value)


class ModelFactoryMeta(type):
    """
    Metaclass for `ModelFactory` classes.

    This metaclass is responsible for processing `ModelFactory` definitions,
    inheriting fields and mappings from parent factories, associating the
    correct Edgy model, initializing Faker, and performing an optional
    validation of the factory's ability to build a model.

    It ensures that each `ModelFactory` subclass has the necessary metadata
    (`MetaInfo`) to generate valid Edgy model instances.
    """

    def __new__(
        cls,
        factory_name: str,
        bases: tuple[type, ...],
        attrs: dict[str, Any],
        meta_info_class: type[MetaInfo] = MetaInfo,
        model_validation: Literal["none", "warn", "error", "pedantic"] = "warn",
        **kwargs: Any,
    ) -> type[ModelFactory]:
        """
        Creates a new `ModelFactory` class.

        Parameters:
            cls (type): The metaclass itself.
            factory_name (str): The name of the `ModelFactory` class being created.
            bases (tuple[type, ...]): A tuple of base classes for the new factory.
            attrs (dict[str, Any]): A dictionary of attributes defined in the
                                    `ModelFactory` class.
            meta_info_class (type[MetaInfo], optional): The `MetaInfo` class to use.
                                                        Defaults to `MetaInfo`.
            model_validation (Literal["none", "warn", "error", "pedantic"], optional):
                Controls how the factory validates its ability to produce a model:
                -   `"none"`: No validation.
                -   `"warn"`: Logs a warning if validation fails.
                -   `"error"`: Raises an exception if validation fails (non-`ValidationError`).
                -   `"pedantic"`: Raises any exception, including `ValidationError`,
                                  if validation fails.
                Defaults to `"warn"`.
            **kwargs (Any): Additional keyword arguments passed to `type.__new__`.

        Returns:
            type[ModelFactory]: The newly created `ModelFactory` class.

        Raises:
            ImportError: If "Faker" is not installed.
            InvalidModelError: If no model is specified in the `Meta` class,
                               or if the specified model is not a valid Edgy model.
            Exception: Based on `model_validation` setting, if the factory fails
                       to build a sample model.
        """
        # If this is the base `ModelFactory` class itself (or not a subclass of
        # another ModelFactory), just create it normally.
        if not any(True for parent in bases if isinstance(parent, ModelFactoryMeta)):
            return super().__new__(cls, factory_name, bases, attrs, **kwargs)  # type: ignore

        # Ensure Faker is installed.
        try:
            from faker import Faker
        except ImportError:
            raise ImportError('"Faker" is required for the ModelFactory.') from None

        faker = Faker()  # Initialize Faker.

        # Pop the 'Meta' inner class if it exists.
        meta_class: Any = attrs.pop("Meta", None)
        fields: dict[str, FactoryField] = {}
        mappings: dict[str, FactoryCallback] = {}

        # Collect mappings from the current factory's Meta.
        current_mapping: dict[str, FactoryCallback | None] = (
            getattr(meta_class, "mappings", None) or {}
        )
        for name, mapping in current_mapping.items():
            mappings.setdefault(name, mapping)

        # Inherit fields and mappings from parent factory classes.
        for base in bases:
            for sub in getmro(base):  # Get method resolution order for proper inheritance.
                meta: Any = getattr(sub, "meta", None)
                if isinstance(meta, MetaInfo):  # Ensure it's a factory MetaInfo.
                    # Inherit mappings.
                    for name, mapping in meta.mappings.items():
                        mappings.setdefault(name, mapping)
                    # Inherit fields.
                    for name, field in meta.fields.items():
                        if field.no_copy:  # Skip fields marked not to be copied.
                            continue
                        # Warn if a field's type has no corresponding mapping.
                        if not field.callback and field.get_field_type() not in mappings:
                            terminal.write_warning(
                                f'Mapping for field type: "{field.get_field_type()}" '
                                f'not found. Skip field: "{field.name}".'
                                f'\nDiffering ModelFactory field name: "{field.original_name}".'
                                if field.original_name != field.name
                                else ""
                            )
                        else:
                            # Add a copy of the field to ensure proper instance-level config.
                            fields.setdefault(name, field.__copy__())

        # Add the default mappings from `DEFAULT_MAPPING`.
        for name, mapping in DEFAULT_MAPPING.items():
            mappings.setdefault(name, mapping)

        # Get the associated Edgy model from the 'Meta' class.
        db_model: type[Model] | str | None = getattr(meta_class, "model", None)
        if db_model is None:
            raise InvalidModelError("Model is required for a factory.") from None

        # If the model is provided as a string, attempt to load it.
        if isinstance(db_model, str):
            db_model = cast(type["Model"], monkay.load(db_model))

        # Validate that the specified model is an actual Edgy model.
        if not is_class_and_subclass(db_model, Model):
            db_model_name = db_model.__name__ if isclass(db_model) else type(db_model).__name__
            raise InvalidModelError(f"Class {db_model_name} is not an Edgy model.") from None

        # Create the `MetaInfo` instance for this new factory.
        meta_info = meta_info_class(model=db_model, faker=faker, mappings=mappings)

        defaults: dict[str, Any] = {}
        # Process fields defined directly on the factory class.
        for key in list(attrs.keys()):  # Iterate over a copy of keys as attrs might change.
            if key in ("meta", "exclude_autoincrement"):  # Skip metaclass specific attributes.
                continue
            value: Any = attrs.get(key)
            if isinstance(value, FactoryField):
                value.original_name = key  # Store original name for debugging.
                del attrs[key]  # Remove from attrs to prevent being normal attribute.
                value.name = field_name = value.name or key  # Set internal name.
                # Warn if a FactoryField lacks a callback and no mapping exists for its type.
                if (
                    not value.callback
                    and value.get_field_type(db_model_meta=db_model.meta) not in mappings
                ):
                    terminal.write_warning(
                        f'Mapping for field type: "{value.get_field_type(db_model_meta=db_model.meta)}" '
                        f'not found. Skip field: "{value.name}".'
                        f'\nDiffering ModelFactory field name: "{value.original_name}".'
                        if value.original_name != value.name
                        else ""
                    )
                else:
                    fields[field_name] = value  # Add to collected fields.
            elif key in db_model.meta.fields:
                # If it's a direct attribute and a model field, treat it as a default value.
                defaults[key] = value

        # Automatically create `FactoryField` for model fields not explicitly defined in the factory.
        for db_field_name in db_model.meta.fields:
            if db_field_name not in fields:
                field = FactoryField(name=db_field_name, no_copy=True)
                field.original_name = db_field_name
                field_type = field.get_field_type(db_model_meta=db_model.meta)
                # Check if a mapping exists for this field type.
                if field_type not in meta_info.mappings:
                    terminal.write_warning(
                        f'Mapping for field type: "{field_type}" not found. '
                        f'Skip field: "{field.name}".'
                        f'\nDiffering ModelFactory field name: "{field.original_name}".'
                        if field.original_name != field.name
                        else ""
                    )
                else:
                    mapping_result = meta_info.mappings.get(field_type)
                    # Ignore `None` mappings, which are used to explicitly exclude fields.
                    if mapping_result:
                        fields[field.name] = field

        meta_info.fields = fields  # Assign the final collected fields.
        attrs["meta"] = meta_info  # Attach `MetaInfo` to the factory class.

        # Create the new factory class using the standard `type.__new__`.
        new_class = cast(
            type["ModelFactory"], super().__new__(cls, factory_name, bases, attrs, **kwargs)
        )
        # Assign the collected default values.
        new_class.__defaults__ = defaults

        # Set the 'owner' attribute on all `FactoryField` instances to the new class.
        for field in fields.values():
            field.owner = new_class

        # Perform model validation based on the `model_validation` setting.
        if model_validation != "none":
            try:
                # Attempt to build a sample model without updating call counts for this validation.
                new_class().build(callcounts={})
            except ValidationError as exc:
                # If a Pydantic ValidationError occurs:
                if model_validation == "pedantic":
                    raise exc  # Re-raise if in pedantic mode.
            except Exception as exc:
                # If any other exception occurs:
                if model_validation == "error" or model_validation == "pedantic":
                    raise exc  # Re-raise if in error or pedantic mode.
                terminal.write_warning(
                    f'"{factory_name}" failed producing a valid sample model: "{exc!r}".'
                )
        return new_class
