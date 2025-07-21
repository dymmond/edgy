from __future__ import annotations

import datetime
from functools import partial
from typing import TYPE_CHECKING, Any

from edgy.core.db.context_vars import (
    CURRENT_FIELD_CONTEXT,
    CURRENT_INSTANCE,
    CURRENT_PHASE,
    EXPLICIT_SPECIFIED_VALUES,
)
from edgy.core.db.fields.base import Field
from edgy.core.db.fields.factories import FieldFactory
from edgy.core.db.fields.types import BaseFieldType
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    import zoneinfo


# Keywords to exclude from kwargs when initializing a field factory.
CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


class IncrementOnSaveBaseField(Field):
    """
    A base field class that provides automatic incrementing of its value upon saving.

    This field allows specifying an `increment_on_save` value. When a model
    containing this field is saved, its value will be increased by this
    specified amount. This is useful for counter-like fields.

    Attributes:
        increment_on_save (int): The amount by which the field's value will
                                 be incremented on each save operation. Defaults to 0.
    """

    increment_on_save: int = 0

    def __init__(self, **kwargs: Any) -> None:
        """
        Initializes the `IncrementOnSaveBaseField`.

        If `increment_on_save` is non-zero, it sets a custom `pre_save_callback`
        to handle the incrementing logic.
        """
        super().__init__(
            **kwargs,
        )
        if self.increment_on_save != 0:
            self.pre_save_callback = self._notset_pre_save_callback

    async def _notset_pre_save_callback(
        self, value: Any, original_value: Any, is_update: bool
    ) -> dict[str, Any]:
        """
        Asynchronous pre-save callback for `increment_on_save` functionality.

        This callback is triggered before a model containing this field is saved.
        It checks if the field's value was explicitly provided. If not, it handles
        the increment logic based on whether it's an insert or update operation.

        Args:
            value (Any): The current value of the field.
            original_value (Any): The value of the field before any changes (for updates).
            is_update (bool): `True` if the operation is an update, `False` for an insert.

        Returns:
            dict[str, Any]: A dictionary containing the field's name and its new value,
                            or an empty dictionary if no change is needed.
        """
        # FIXME: we are stuck on an old version of field before copy, so replace self
        # Workaround for field copy issues, retrieve current field context.
        self = CURRENT_FIELD_CONTEXT.get()["field"]  # type: ignore
        explicit_values = EXPLICIT_SPECIFIED_VALUES.get()

        # If the value was explicitly specified by the user, do nothing.
        if explicit_values is not None and self.name in explicit_values:
            return {}

        model_or_query = CURRENT_INSTANCE.get()

        if not is_update:
            # For inserts:
            if original_value is None:
                # If no original value, use the default value.
                return {self.name: self.get_default_value()}
            else:
                # If original value exists, increment it.
                return {self.name: value + self.increment_on_save}
        elif not self.primary_key:
            # For updates (non-primary key fields):
            # Increment the value directly in the database using a SQLAlchemy column expression.
            return {self.name: (model_or_query).table.columns[self.name] + self.increment_on_save}
        else:
            # For updates (primary key fields):
            # Primary keys usually shouldn't be incremented directly after insertion.
            return {}

    def get_default_values(
        self,
        field_name: str,
        cleaned_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Overrides `get_default_values` to handle `increment_on_save` during updates.

        During a "prepare_update" phase, if `increment_on_save` is active,
        this field's default should be `None` to allow the `_notset_pre_save_callback`
        to handle the increment.
        """
        if self.increment_on_save != 0:
            phase = CURRENT_PHASE.get()
            if phase == "prepare_update":
                return {field_name: None}  # Do not provide a default during update preparation.
        return super().get_default_values(field_name, cleaned_data)

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        """
        Overrides `to_model` to adjust field behavior after an update.

        After a "post_update" phase, if `increment_on_save` is active and the
        field is not a primary key, it clears the field from the instance's
        dictionary. This prevents the old value from being used if the field
        was incremented directly in the database.
        """
        phase = CURRENT_PHASE.get()
        instance = CURRENT_INSTANCE.get()
        if self.increment_on_save != 0 and not self.primary_key and phase == "post_update":
            # Remove the field from the instance's dict to force a reload from DB if needed.
            instance.__dict__.pop(field_name, None)
            return {}
        return super().to_model(field_name, value)


class TimezonedField:
    """
    A mixin class for fields that handle timezone awareness for `datetime` and `date` objects.

    This class provides methods to convert and standardize `datetime` objects
    based on default, forced, or removal of timezones.
    """

    default_timezone: zoneinfo.ZoneInfo | None
    force_timezone: zoneinfo.ZoneInfo | None
    remove_timezone: bool
    field_type: Any  # Expected to be datetime.datetime or datetime.date

    def _convert_datetime(self, value: datetime.datetime) -> datetime.datetime | datetime.date:
        """
        Converts a `datetime` object based on timezone settings.

        Args:
            value (datetime.datetime): The datetime object to convert.

        Returns:
            datetime.datetime | datetime.date: The timezone-adjusted datetime or date object.
        """
        # Apply default timezone if none is present.
        if value.tzinfo is None and self.default_timezone is not None:
            value = value.replace(tzinfo=self.default_timezone)
        # Force to a specific timezone if different.
        if self.force_timezone is not None and value.tzinfo != self.force_timezone:
            if value.tzinfo is None:
                # If no timezone, just set the forced one.
                value = value.replace(tzinfo=self.force_timezone)
            else:
                # Convert to the forced timezone.
                value = value.astimezone(self.force_timezone)
        # Remove timezone information if requested.
        if self.remove_timezone:
            value = value.replace(tzinfo=None)
        # Convert to date if the field type is date.
        if self.field_type is datetime.date:
            return value.date()
        return value

    def check(self, value: Any) -> datetime.datetime | datetime.date | None:
        """
        Validates and converts a value into a timezone-aware datetime or date object.

        Handles various input types: None, datetime, int/float (timestamps), str (ISO format),
        and date objects.

        Args:
            value (Any): The input value to convert.

        Returns:
            datetime.datetime | datetime.date | None: The converted datetime/date object, or None.

        Raises:
            ValueError: If an unsupported type is provided.
        """
        if value is None:
            return None
        elif isinstance(value, datetime.datetime):
            return self._convert_datetime(value)
        elif isinstance(value, int | float):
            # Convert timestamp to datetime, then apply timezone.
            return self._convert_datetime(
                datetime.datetime.fromtimestamp(value, self.default_timezone)
            )
        elif isinstance(value, str):
            # Parse ISO formatted string to datetime, then apply timezone.
            return self._convert_datetime(datetime.datetime.fromisoformat(value))
        elif isinstance(value, datetime.date):
            # datetime is a subclass of date, so check datetime first.
            # If it's a DateField, just return the date.
            if self.field_type is datetime.date:
                return value
            # Otherwise, convert date to datetime and then apply timezone.
            return self._convert_datetime(
                datetime.datetime(year=value.year, month=value.month, day=value.day)
            )
        else:
            raise ValueError(f"Invalid type detected: {type(value)}")

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, datetime.datetime | datetime.date | None]:
        """
        Converts the input object to a datetime or date model representation.
        """
        return {field_name: self.check(value)}

    def get_default_value(self) -> Any:
        """
        Retrieves the default value for the field, applying timezone conversion.
        """
        return self.check(super().get_default_value())


class AutoNowMixin(FieldFactory):
    """
    A mixin for field factories that provides `auto_now` and `auto_now_add` functionality.

    This mixin automatically sets the field's value to the current datetime
    (or date) upon creation (`auto_now_add`) or upon every save (`auto_now`).
    It also handles timezone considerations.
    """

    def __new__(
        cls,
        *,
        auto_now: bool | None = False,
        auto_now_add: bool | None = False,
        default_timezone: zoneinfo.ZoneInfo | None = None,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Creates a new field instance with auto-now/auto-now-add capabilities.

        Args:
            auto_now (bool | None): If `True`, the field is updated to the current
                                    datetime/date on every save.
            auto_now_add (bool | None): If `True`, the field is set to the current
                                        datetime/date only on creation.
            default_timezone (Optional[zoneinfo.ZoneInfo]): The default timezone to use
                                                           when creating new datetime objects.
            **kwargs (Any): Additional keyword arguments for the field.

        Returns:
            BaseFieldType: The constructed field instance.

        Raises:
            FieldDefinitionError: If both `auto_now` and `auto_now_add` are `True`.
        """
        if auto_now_add and auto_now:
            raise FieldDefinitionError("'auto_now' and 'auto_now_add' cannot be both True")

        # Set read_only and inject_default_on_partial_update based on auto_now/auto_now_add.
        if auto_now_add or auto_now:
            kwargs.setdefault("read_only", True)
            kwargs["inject_default_on_partial_update"] = auto_now

        # Merge local arguments into kwargs.
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }

        if auto_now_add or auto_now:
            # Use `datetime.datetime.now` with `partial` to handle the `default_timezone`.
            # Note: `date.today()` does not support timezones directly, so we use datetime.
            kwargs["default"] = partial(datetime.datetime.now, default_timezone)
            # Ensure no automatic server-side default calculation happens, as we handle it.
            kwargs.setdefault("auto_compute_server_default", False)

        return super().__new__(cls, **kwargs)
