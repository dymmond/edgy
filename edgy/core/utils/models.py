import typing
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional, Type

from orjson import OPT_OMIT_MICROSECONDS  # noqa
from orjson import OPT_SERIALIZE_NUMPY  # noqa
from orjson import dumps

from edgy.core.db.fields import DateField, DateTimeField

if TYPE_CHECKING:
    from edgy import Model


class DateParser:
    """
    Utils used by the Registry
    """

    def _update_auto_now_fields(self, values: Any, fields: Any) -> Any:
        """
        Updates the auto fields
        """
        for k, v in fields.items():
            if isinstance(v, (DateField, DateTimeField)) and v.auto_now:  # type: ignore
                values[k] = v.get_default_value()  # type: ignore
        return values

    def _resolve_value(self, value: typing.Any) -> typing.Any:
        if isinstance(value, dict):
            return dumps(
                value,
                option=OPT_SERIALIZE_NUMPY | OPT_OMIT_MICROSECONDS,
            ).decode("utf-8")
        elif isinstance(value, Enum):
            return value.name
        return value


class ModelParser:
    """
    Parser for the models operations of extraction of data from a given model.
    """

    def extract_values_from_field(
        self, extracted_values: Any, model_class: Optional[Type["Model"]] = None
    ) -> Any:
        model_cls = model_class or self
        validated = {}
        for name, field in model_cls.fields.items():
            if field.read_only:
                continue

            if name not in extracted_values:
                if field.has_default():
                    validated[name] = field.get_default_value()
                continue

            item = extracted_values[name]
            value = field.check(item)
            validated[name] = value
        return validated

    def extract_db_fields_from_model(self, model_class: Type["Model"]):
        """
        Extacts all the db fields and excludes the related_names since those
        are simply relations.
        """
        related_names = model_class.meta.related_names
        return {k: v for k, v in model_class.__dict__.items() if k not in related_names}
