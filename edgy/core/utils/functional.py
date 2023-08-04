"""
All functional common to Edgy
"""
from typing import Any, Dict, Tuple, Union

from edgy.core.db.fields.base import BaseField

edgy_setattr = object.__setattr__


def extract_field_annotations_and_defaults(
    attrs: Dict[Any, Any]
) -> Tuple[Dict[Any, Any], Dict[Any, Any]]:
    """
    Extracts annotations from class namespace dict and triggers
    extraction of ormar model_fields.
    """
    key = "__annotations__"
    attrs[key] = attrs.get(key, {})
    attrs, model_fields = populate_pydantic_default_values(attrs)
    return attrs, model_fields


def get_model_fields(attrs: Union[Dict, Any]) -> Dict:
    """
    Gets all the fields in current model class that are Edgy Fields.
    """
    return {k: v for k, v in attrs.items() if isinstance(v, BaseField)}


def populate_pydantic_default_values(attrs: Dict) -> Tuple[Dict, Dict]:
    """
    Making sure the fields from Edgy are the ones being validated by Edgy models
    and delegates the validations from pydantic to that functionality.
    """
    model_fields = {}
    potential_fields = {}

    potential_fields.update(get_model_fields(attrs))
    for field_name, field in potential_fields.items():
        field.name = field_name

        default_type = field.field_type if not field.null else Union[field.field_type, None]
        overwrite_type = (
            field.__original_type__ if field.field_type != field.__original_type__ else None
        )
        field.annotation = overwrite_type or default_type
        model_fields[field_name] = field
        attrs["__annotations__"][field_name] = overwrite_type or default_type
    return attrs, model_fields
