import datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Optional, Union

from edgy.core.db.context_vars import CURRENT_INSTANCE, CURRENT_PHASE, EXPLICIT_SPECIFIED_VALUES
from edgy.core.db.fields.base import Field
from edgy.core.db.fields.factories import FieldFactory
from edgy.core.db.fields.types import BaseFieldType
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    import zoneinfo

    from edgy.core.db.models.types import BaseModelType


CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


class IncrementOnSaveBaseField(Field):
    increment_on_save: int = 0

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            **kwargs,
        )
        if self.increment_on_save != 0:
            self.pre_save_callback = self._notset_pre_save_callback

    async def _notset_pre_save_callback(
        self, value: Any, original_value: Any, force_insert: bool, instance: "BaseModelType"
    ) -> dict[str, Any]:
        explicit_values = EXPLICIT_SPECIFIED_VALUES.get()
        if explicit_values is not None and self.name in explicit_values:
            return {}
        model_or_query = CURRENT_INSTANCE.get()

        if force_insert:
            if original_value is None:
                return {self.name: self.get_default_value()}
            else:
                return {self.name: value + self.increment_on_save}
        elif not self.primary_key:
            # update path
            return {
                self.name: (
                    model_or_query if model_or_query is not None else instance
                ).table.columns[self.name]
                + self.increment_on_save
            }
        else:
            # update path
            return {}

    def get_default_values(
        self,
        field_name: str,
        cleaned_data: dict[str, Any],
    ) -> dict[str, Any]:
        if self.increment_on_save != 0:
            phase = CURRENT_PHASE.get()
            if phase == "prepare_update":
                return {field_name: None}
        return super().get_default_values(field_name, cleaned_data)

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        phase = CURRENT_PHASE.get()
        instance = CURRENT_INSTANCE.get()
        if self.increment_on_save != 0 and not self.primary_key and phase == "post_update":
            # a bit dirty but works
            instance.__dict__.pop(field_name, None)
            return {}
        return super().to_model(field_name, value)


class TimezonedField:
    default_timezone: Optional["zoneinfo.ZoneInfo"]
    force_timezone: Optional["zoneinfo.ZoneInfo"]
    remove_timezone: bool

    def _convert_datetime(
        self, value: datetime.datetime
    ) -> Union[datetime.datetime, datetime.date]:
        if value.tzinfo is None and self.default_timezone is not None:
            value = value.replace(tzinfo=self.default_timezone)
        if self.force_timezone is not None and value.tzinfo != self.force_timezone:
            if value.tzinfo is None:
                value = value.replace(tzinfo=self.force_timezone)
            else:
                value = value.astimezone(self.force_timezone)
        if self.remove_timezone:
            value = value.replace(tzinfo=None)
        if self.field_type is datetime.date:
            return value.date()
        return value

    def check(self, value: Any) -> Optional[Union[datetime.datetime, datetime.date]]:
        if value is None:
            return None
        elif isinstance(value, datetime.datetime):
            return self._convert_datetime(value)
        elif isinstance(value, (int, float)):
            return self._convert_datetime(
                datetime.datetime.fromtimestamp(value, self.default_timezone)
            )
        elif isinstance(value, str):
            return self._convert_datetime(datetime.datetime.fromisoformat(value))
        elif isinstance(value, datetime.date):
            # datetime is subclass, so check datetime first

            # don't touch dates when DateField
            if self.field_type is datetime.date:
                return value
            return self._convert_datetime(
                datetime.datetime(year=value.year, month=value.month, day=value.day)
            )
        else:
            raise ValueError(f"Invalid type detected: {type(value)}")

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Optional[Union[datetime.datetime, datetime.date]]]:
        """
        Convert input object to datetime
        """
        return {field_name: self.check(value)}

    def get_default_value(self) -> Any:
        return self.check(super().get_default_value())


class AutoNowMixin(FieldFactory):
    def __new__(  # type: ignore
        cls,
        *,
        auto_now: Optional[bool] = False,
        auto_now_add: Optional[bool] = False,
        default_timezone: Optional["zoneinfo.ZoneInfo"] = None,
        **kwargs: Any,
    ) -> BaseFieldType:
        if auto_now_add and auto_now:
            raise FieldDefinitionError("'auto_now' and 'auto_now_add' cannot be both True")

        if auto_now_add or auto_now:
            kwargs.setdefault("read_only", True)
            kwargs["inject_default_on_partial_update"] = auto_now

        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        if auto_now_add or auto_now:
            # date.today cannot handle timezone so use alway datetime and convert back to date
            kwargs["default"] = partial(datetime.datetime.now, default_timezone)
            # ensure no automatic calculation happens
            kwargs.setdefault("auto_compute_server_default", False)
        return super().__new__(cls, **kwargs)
