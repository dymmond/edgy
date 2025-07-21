from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from monkay import load
from pydantic._internal._model_construction import ModelMetaclass

from edgy.core.db import models
from edgy.core.db.models.metaclasses import handle_annotations
from edgy.core.marshalls.config import ConfigMarshall
from edgy.core.marshalls.fields import BaseMarshallField
from edgy.core.utils.functional import extract_field_annotations_and_defaults
from edgy.exceptions import MarshallFieldDefinitionError

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.marshalls.base import Marshall


def _make_pk_field_readonly(field: BaseFieldType) -> BaseFieldType:
    """
    Helper function to make a primary key field read-only.
    If the field is not a primary key, it is returned as is.
    Otherwise, a copy of the field is made, and its `read_only` attribute is set to True.

    Args:
        field (BaseFieldType): The field to potentially modify.

    Returns:
        BaseFieldType: The original field or a new read-only copy if it's a primary key.
    """
    if not getattr(field, "primary_key", False):
        return field
    # Create a copy to avoid modifying the original field definition.
    field = copy.copy(field)
    field.read_only = True
    return field


class MarshallMeta(ModelMetaclass):
    """
    Metaclass for Edgy Marshalls.

    This metaclass is responsible for:
    1. Processing `marshall_config` to determine which fields from the associated
       Edgy model should be included or excluded in the marshall.
    2. Handling custom fields defined directly on the marshall, including method-based fields.
    3. Applying transformations like making primary keys read-only or excluding autoincrement fields.
    4. Managing the Pydantic model fields and annotations for the marshall class.
    5. Determining if the marshall should be lazy-loaded based on required fields.
    """

    __slots__ = ()  # Optimize memory by not creating a __dict__ for instances of the metaclass.

    def __new__(cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]) -> Any:
        # Initialize variables.
        base_annotations: dict[str, Any] = {}
        show_pk: bool = False
        # Pop 'marshall_config' from attrs; it's a metaclass-level configuration.
        marshall_config: ConfigMarshall | None = attrs.pop("marshall_config", None)
        # Extract field annotations and their default values, specifically for BaseMarshallField.
        attrs, model_fields = extract_field_annotations_and_defaults(attrs, BaseMarshallField)

        # Check if any parent class is also a MarshallMeta. This helps differentiate
        # the base MarshallMeta from subsequent inherited Marshalls.
        has_parents = any(isinstance(parent, MarshallMeta) for parent in bases)

        # If this is the very first MarshallMeta (BaseMarshall itself), just create it.
        if not has_parents:
            return super().__new__(cls, name, bases, attrs)

        # Create the Pydantic model class using the parent ModelMetaclass.
        marshall_class: type[Marshall] = super().__new__(cls, name, bases, attrs)

        # Ensure 'marshall_config' is provided for concrete marshall classes.
        if marshall_config is None:
            raise MarshallFieldDefinitionError(
                "The 'marshall_config' was not found. Make sure it is declared and set."
            )

        # Retrieve and validate the associated Edgy model.
        _model: type[models.Model] | str | None = marshall_config.get("model", None)
        assert _model is not None, "'model' must be declared in the 'ConfigMarshall'."

        # If the model is provided as a string, dynamically load it.
        if isinstance(_model, str):
            model: type[models.Model] = load(_model)
            marshall_config["model"] = model  # Update config with the loaded model class.
        else:
            model = _model

        # Get field inclusion/exclusion lists from marshall_config.
        base_fields_include = marshall_config.get("fields", None)
        base_fields_exclude = marshall_config.get("exclude", None)

        # Validate that 'fields' and 'exclude' are not used simultaneously.
        assert base_fields_include is None or base_fields_exclude is None, (
            "Use either 'fields' or 'exclude', not both."
        )
        # Validate that at least one of 'fields' or 'exclude' is declared.
        assert base_fields_include is not None or base_fields_exclude is not None, (
            "Either 'fields' or 'exclude' must be declared."
        )

        base_marshall_model_fields: dict[str, Any]

        # Determine the base set of fields for the marshall based on include/exclude.
        if base_fields_exclude is not None:
            # Exclude specified fields and any fields already marked for exclusion.
            base_marshall_model_fields = {
                k: v
                for k, v in model.model_fields.items()
                if k not in base_fields_exclude and not getattr(v, "exclude", False)
            }
        elif base_fields_include is not None and "__all__" in base_fields_include:
            # Include all model fields except those explicitly defined on the marshall itself
            # and those already marked for exclusion.
            base_marshall_model_fields = {
                k: v
                for k, v in model.model_fields.items()
                if k not in model_fields and not getattr(v, "exclude", False)
            }
            show_pk = True  # If "__all__" is used, primary keys should be shown.
        else:
            # Include only the explicitly specified fields.
            base_marshall_model_fields = {
                k: v for k, v in model.model_fields.items() if k in base_fields_include
            }

        # Apply `exclude_autoincrement` filter.
        if marshall_config.get("exclude_autoincrement", False):
            base_marshall_model_fields = {
                k: v
                for k, v in base_marshall_model_fields.items()
                if not getattr(v, "autoincrement", False)
            }

        # Apply `primary_key_read_only` transformation.
        if marshall_config.get("primary_key_read_only", False):
            base_marshall_model_fields = {
                k: _make_pk_field_readonly(v) for k, v in base_marshall_model_fields.items()
            }

        # Apply `exclude_read_only` filter.
        if marshall_config.get("exclude_read_only", False):
            base_marshall_model_fields = {
                k: v
                for k, v in base_marshall_model_fields.items()
                if not getattr(v, "read_only", False)
            }

        # Update the base marshall model fields with any fields defined directly on the marshall.
        base_marshall_model_fields.update(model_fields)

        # Identify custom fields (fields defined on the marshall that are not present in the model).
        custom_fields: dict[str, BaseMarshallField] = {}
        for k, v in attrs.items():
            if (
                isinstance(v, BaseMarshallField) and k not in model.meta.fields
            ):  # Check if field is not from the model.
                custom_fields[k] = v

        # Validate custom method-based fields.
        for name, field in custom_fields.items():
            if (
                field.__is_method__  # If it's a method field
                and not field.source  # and no explicit source is given
                and not hasattr(marshall_class, f"get_{name}")  # and no getter method exists
            ):
                raise MarshallFieldDefinitionError(
                    f"Field '{name}' declared but no 'get_{name}' found in "
                    f"'{marshall_class.__name__}'."
                )

        # Update Pydantic's internal model fields for the marshall class.
        model_fields_on_class = getattr(marshall_class, "__pydantic_fields__", None)
        if model_fields_on_class is None:
            model_fields_on_class = marshall_class.model_fields

        # Ensure 'marshall_config' is not accidentally treated as a Pydantic field.
        if "marshall_config" in model_fields_on_class:
            raise MarshallFieldDefinitionError(
                f"'marshall_config' is part of the fields of '{marshall_class.__name__}'. "
                "Did you forget to annotate with 'ClassVar'?"
            )

        # Ensure that the marshall's fields are distinct from the model's fields.
        assert model_fields_on_class is not model.model_fields

        # Remove any temporary fields from `extract_field_annotations_and_defaults`.
        for key in model_fields:
            del model_fields_on_class[key]

        # Add the determined base marshall model fields.
        model_fields_on_class.update(base_marshall_model_fields)

        # Handle annotations for the marshall class.
        annotations: dict[str, Any] = handle_annotations(bases, base_annotations, attrs)
        marshall_class.__init_annotations__ = annotations

        # Set metaclass-level attributes on the marshall class.
        marshall_class.__show_pk__ = show_pk
        marshall_class.__custom_fields__ = custom_fields
        marshall_class.marshall_config = marshall_config

        # Determine required fields for `_setup` method and set `__lazy__` flag.
        required_fields: set[str] = {k for k, v in model.model_fields.items() if v.is_required()}
        marshall_class.__incomplete_fields__ = tuple(
            sorted(name for name in required_fields if name not in model_fields_on_class)
        )
        # If there are incomplete fields, the marshall must be lazy-loaded.
        if marshall_class.__incomplete_fields__:
            marshall_class.__lazy__ = True

        # Rebuild the Pydantic model schema to incorporate all changes.
        marshall_class.model_rebuild(force=True)
        return marshall_class
