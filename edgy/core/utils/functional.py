"""
All functional common to Edgy
"""

from typing import Any, Dict, Tuple, Type, Union

from edgy.core.db.fields.base import BaseField

# bypass __setattr__ method
edgy_setattr = object.__setattr__


def extract_field_annotations_and_defaults(
    attrs: Dict[Any, Any], base_type: Type[BaseField] = BaseField
) -> Tuple[Dict[Any, Any], Dict[Any, Any]]:
    """
    Extracts annotations from class namespace dict and triggers
    extraction of ormar model_fields.
    """
    key = "__annotations__"
    attrs[key] = attrs.get(key, {})
    attrs, model_fields = populate_pydantic_default_values(attrs, base_type)
    return attrs, model_fields


def get_model_fields(attrs: Union[Dict, Any], base_type: Type[BaseField] = BaseField) -> Dict:
    """
    Gets all the fields in current model class that are Edgy Fields.
    """
    return {k: v for k, v in attrs.items() if isinstance(v, base_type)}


def populate_pydantic_default_values(attrs: Dict, base_type: Type[BaseField] = BaseField) -> Tuple[Dict, Dict]:
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

        default_type = field.field_type if not field.null else Union[field.field_type, None]
        overwrite_type = original_type if field.field_type != original_type else None
        field.annotation = overwrite_type or default_type
        model_fields[field_name] = field
        attrs["__annotations__"][field_name] = overwrite_type or default_type
    return attrs, model_fields
