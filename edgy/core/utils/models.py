import typing
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Type

from orjson import OPT_OMIT_MICROSECONDS, OPT_SERIALIZE_NUMPY, dumps
from pydantic import ConfigDict

import edgy
from edgy.core.db.fields.core import BaseField, Field

if TYPE_CHECKING:
    from edgy import Model
    from edgy.core.db.models.metaclasses import MetaInfo


class DateParser:
    def has_auto_now(self, field: Type[BaseField]) -> bool:
        """
        Checks if the field is auto now
        """
        return True if hasattr(field, "auto_now") and field.auto_now else False

    def is_datetime(self, field: Type[BaseField]) -> bool:
        """
        Validates if the field type is a datetime type.
        """
        return bool(field.field_type == datetime)

    def update_auto_now_fields(self, values: Any, fields: Any) -> Any:
        """
        Updates the auto fields
        """
        for name, field in fields.items():
            if isinstance(field, Field) and self.has_auto_now(field) and self.is_datetime(field):
                values[name] = field.get_default_value()  # type: ignore
        return values

    def resolve_value(self, value: typing.Any) -> typing.Any:
        if isinstance(value, dict):
            return dumps(
                value,
                option=OPT_SERIALIZE_NUMPY | OPT_OMIT_MICROSECONDS,
            ).decode("utf-8")
        elif isinstance(value, Enum):
            return value.name
        return value


class ModelParser:
    def extract_values_from_field(
        self, extracted_values: Any, model_class: Optional[Type["Model"]] = None
    ) -> Any:
        """
        Extracts all the deffault values from the given fields and returns the raw
        value corresponding to each field.
        """
        model_cls = model_class or self
        validated = {}
        for name, field in model_cls.fields.items():
            if field.read_only:
                if field.has_default():
                    validated[name] = field.get_default_value()
                continue

            if name not in extracted_values:
                if field.has_default():
                    validated[name] = field.get_default_value()
                continue

            item = extracted_values[name]
            value = field.check(item) if hasattr(field, "check") else None
            validated[name] = value
        return validated

    def extract_db_fields_from_model(self, model_class: Type["Model"]):
        """
        Extacts all the db fields and excludes the related_names since those
        are simply relations.
        """
        related_names = model_class.meta.related_names
        return {k: v for k, v in model_class.__dict__.items() if k not in related_names}


def create_edgy_model(
    __name__: str,
    __definitions__: Dict[Any, Any],
    __module__: str,
    __metadata__: Type["MetaInfo"],
    __qualname__: Optional[str] = None,
    __config__: Optional[ConfigDict] = None,
    __bases__: Optional[Tuple[Type["Model"]]] = None,
    __partial__: bool = False,
) -> Type["Model"]:
    """
    Generates an `edgy.Model` with all the required definitions to generate the pydantic
    like model.
    """
    if not __bases__:
        __bases__ = (edgy.Model,)

    qualname = __qualname__ or __name__
    core_definitions = {
        "__module__": __module__,
        "__qualname__": qualname,
        "partial_model": __partial__,
        "Meta": __metadata__,
    }
    core_definitions.update(**__definitions__)

    if __config__:
        core_definitions.update(**{"model_config": __config__})

    model: Type["Model"] = type(__name__, __bases__, core_definitions)
    return model
