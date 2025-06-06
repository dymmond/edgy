"""
All functional common to Edgy
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from edgy.core.db.fields.types import BaseFieldType

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def extract_field_annotations_and_defaults(
    attrs: dict[Any, Any], base_type: type[FieldInfo] | type[BaseFieldType] = BaseFieldType
) -> tuple[dict[Any, Any], dict[Any, Any]]:
    """
    Extracts annotations from class namespace dict and triggers
    extraction of ormar model_fields.
    """
    key = "__annotations__"
    attrs[key] = attrs.get(key, {})
    attrs, model_fields = populate_pydantic_default_values(attrs, base_type)
    return attrs, model_fields


def get_model_fields(
    attrs: dict | Any, base_type: type[FieldInfo] | type[BaseFieldType] = BaseFieldType
) -> dict:
    """
    Gets all the fields in current model class that are Edgy Fields.
    """
    return {k: v for k, v in attrs.items() if isinstance(v, base_type)}


def populate_pydantic_default_values(
    attrs: dict, base_type: type[FieldInfo] | type[BaseFieldType] = BaseFieldType
) -> tuple[dict, dict]:
    """
    Making sure the fields from Edgy are the ones being validated by Edgy models
    and delegates the validations from pydantic to that functionality.
    """
    model_fields = {}
    potential_fields = {}

    potential_fields.update(get_model_fields(attrs, base_type))
    for field_name, field in potential_fields.items():
        field.name = field_name
        original_type = getattr(field, "__original_type__", None)

        default_type = field.field_type if not field.null else None | field.field_type
        overwrite_type = original_type if field.field_type != original_type else None
        field.annotation = overwrite_type or default_type
        model_fields[field_name] = field
        attrs["__annotations__"][field_name] = overwrite_type or default_type
    return attrs, model_fields
