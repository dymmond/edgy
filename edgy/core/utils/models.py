import typing
from enum import Enum
from typing import Any

from orjson import OPT_OMIT_MICROSECONDS  # noqa
from orjson import OPT_SERIALIZE_NUMPY  # noqa
from orjson import dumps

from edgy.core.db.fields import DateField, DateTimeField


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
                values[k] = v.validator.get_default_value()  # type: ignore
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
