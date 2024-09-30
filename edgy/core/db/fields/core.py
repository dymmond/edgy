import datetime
import decimal
import enum
import ipaddress
import uuid
from collections.abc import Sequence
from enum import EnumMeta
from functools import partial
from re import Pattern
from typing import TYPE_CHECKING, Any, Optional, Union

import pydantic
import sqlalchemy
from pydantic import EmailStr

from edgy.core.db.context_vars import CURRENT_INSTANCE, CURRENT_PHASE, EXPLICIT_SPECIFIED_VALUES
from edgy.core.db.fields._internal import IPAddress
from edgy.core.db.fields._validators import IPV4_REGEX, IPV6_REGEX
from edgy.core.db.fields.base import Field
from edgy.core.db.fields.factories import FieldFactory
from edgy.core.db.fields.types import BaseFieldType
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    import zoneinfo

    from edgy.core.db.models.types import BaseModelType


CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


class CharField(FieldFactory, str):
    """String field representation that constructs the Field class and populates the values"""

    field_type = str

    def __new__(  # type: ignore
        cls,
        *,
        max_length: Optional[int] = 0,
        min_length: Optional[int] = None,
        regex: Union[str, Pattern] = None,
        pattern: Union[str, Pattern] = None,
        **kwargs: Any,
    ) -> BaseFieldType:
        if pattern is None:
            pattern = regex
        del regex
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }

        return super().__new__(cls, **kwargs)

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        max_length = kwargs.get("max_length", 0)
        if max_length <= 0:
            raise FieldDefinitionError(detail=f"'max_length' is required for {cls.__name__}")

        min_length = kwargs.get("min_length")
        pattern = kwargs.get("regex")

        assert min_length is None or isinstance(min_length, int)
        assert max_length is None or isinstance(max_length, int)
        assert pattern is None or isinstance(pattern, (str, Pattern))

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.String(
            length=kwargs.get("max_length"), collation=kwargs.get("collation")
        )


class TextField(FieldFactory, str):
    """String representation of a text field which means no max_length required"""

    field_type = str

    def __new__(
        cls,
        *,
        min_length: int = 0,
        max_length: Optional[int] = None,
        regex: Union[str, Pattern] = None,
        pattern: Union[str, Pattern] = None,
        **kwargs: Any,
    ) -> BaseFieldType:
        if pattern is None:
            pattern = regex
        del regex
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Text(collation=kwargs.get("collation"))


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
            if phase in "prepare_update":
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


class IntegerField(FieldFactory, int):
    """
    Integer field factory that construct Field classes and populated their values.
    """

    field_type = int
    field_bases = (IncrementOnSaveBaseField,)

    def __new__(  # type: ignore
        cls,
        *,
        ge: Union[int, float, decimal.Decimal, None] = None,
        gt: Union[int, float, decimal.Decimal, None] = None,
        le: Union[int, float, decimal.Decimal, None] = None,
        lt: Union[int, float, decimal.Decimal, None] = None,
        multiple_of: Optional[int] = None,
        increment_on_save: int = 0,
        **kwargs: Any,
    ) -> BaseFieldType:
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in ["cls", "__class__", "kwargs"]},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Integer()

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        increment_on_save = kwargs.get("increment_on_save", 0)
        if increment_on_save == 0 and kwargs.get("primary_key", False):
            kwargs.setdefault("autoincrement", True)
        if increment_on_save != 0:
            if kwargs.get("autoincrement"):
                raise FieldDefinitionError(
                    detail="'autoincrement' is incompatible with 'increment_on_save'"
                )
            if kwargs.get("null"):
                raise FieldDefinitionError(
                    detail="'null' is incompatible with 'increment_on_save'"
                )
            kwargs.setdefault("read_only", True)
            kwargs["inject_default_on_partial_update"] = True


class FloatField(FieldFactory, float):
    """Representation of a int32 and int64"""

    field_type = float

    def __new__(  # type: ignore
        cls,
        *,
        ge: Union[int, float, decimal.Decimal, None] = None,
        gt: Union[int, float, decimal.Decimal, None] = None,
        le: Union[int, float, decimal.Decimal, None] = None,
        lt: Union[int, float, decimal.Decimal, None] = None,
        **kwargs: Any,
    ) -> BaseFieldType:
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Float(asdecimal=False)


class BigIntegerField(IntegerField):
    """Representation of big integer field"""

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        super().validate(kwargs)
        if kwargs.get("autoincrement", False):
            kwargs.setdefault("skip_reflection_type_check", True)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        # sqlite special we cannot have a big IntegerField as PK
        if kwargs.get("autoincrement"):
            return sqlalchemy.BigInteger().with_variant(sqlalchemy.Integer, "sqlite")
        return sqlalchemy.BigInteger()


class SmallIntegerField(IntegerField):
    """Represents a small integer field"""

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.SmallInteger()


class DecimalField(FieldFactory, decimal.Decimal):
    field_type = decimal.Decimal

    def __new__(  # type: ignore
        cls,
        *,
        ge: Union[int, float, decimal.Decimal, None] = None,
        gt: Union[int, float, decimal.Decimal, None] = None,
        le: Union[int, float, decimal.Decimal, None] = None,
        lt: Union[int, float, decimal.Decimal, None] = None,
        multiple_of: Union[int, decimal.Decimal, None] = None,
        max_digits: Optional[int] = None,
        decimal_places: Optional[int] = None,
        **kwargs: Any,
    ) -> BaseFieldType:
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in ["cls", "__class__", "kwargs"]},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Numeric(
            precision=kwargs.get("max_digits"), scale=kwargs.get("decimal_places"), asdecimal=True
        )

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        super().validate(kwargs)

        decimal_places = kwargs.get("decimal_places")
        if decimal_places is None or decimal_places < 0:
            raise FieldDefinitionError("decimal_places are required for DecimalField")


class BooleanField(FieldFactory, int):
    """Representation of a boolean"""

    field_type = bool

    def __new__(  # type: ignore
        cls,
        *,
        default: Optional[bool] = False,
        **kwargs: Any,
    ) -> BaseFieldType:
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Boolean()


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
        return super().__new__(cls, **kwargs)


class DateTimeField(AutoNowMixin, datetime.datetime):
    """Representation of a datetime field"""

    field_type = datetime.datetime
    field_bases = (TimezonedField, Field)

    def __new__(  # type: ignore
        cls,
        *,
        auto_now: Optional[bool] = False,
        auto_now_add: Optional[bool] = False,
        default_timezone: Optional["zoneinfo.ZoneInfo"] = None,
        force_timezone: Optional["zoneinfo.ZoneInfo"] = None,
        remove_timezone: bool = False,
        **kwargs: Any,
    ) -> BaseFieldType:
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        kwargs.setdefault("with_timezone", not remove_timezone)
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, with_timezone: bool = True, **kwargs: Any) -> Any:
        return sqlalchemy.DateTime(with_timezone)

    @classmethod
    def get_default_values(
        cls,
        field_obj: Field,
        field_name: str,
        cleaned_data: dict[str, Any],
        original_fn: Any = None,
    ) -> Any:
        phase = CURRENT_PHASE.get()
        if field_obj.auto_now_add and phase == "prepare_update":
            return {}
        return original_fn(field_name, cleaned_data)


class DateField(AutoNowMixin, datetime.date):
    """Representation of a date field"""

    field_type = datetime.date
    field_bases = (TimezonedField, Field)

    def __new__(  # type: ignore
        cls,
        *,
        auto_now: Optional[bool] = False,
        auto_now_add: Optional[bool] = False,
        default_timezone: Optional["zoneinfo.ZoneInfo"] = None,
        force_timezone: Optional["zoneinfo.ZoneInfo"] = None,
        **kwargs: Any,
    ) -> BaseFieldType:
        # the datetimes lose the information anyway
        kwargs["remove_timezone"] = False

        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Date()


class TimeField(FieldFactory, datetime.time):
    """Representation of a time field"""

    field_type = datetime.time

    def __new__(cls, **kwargs: Any) -> BaseFieldType:  # type: ignore
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Time(kwargs.get("with_timezone") or False)


class JSONField(FieldFactory, pydantic.Json):  # type: ignore
    """Representation of a JSONField"""

    field_type = Any

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.JSON()


class BinaryField(FieldFactory, bytes):
    """Representation of a binary"""

    field_type = bytes

    def __new__(cls, *, max_length: Optional[int] = None, **kwargs: Any) -> BaseFieldType:  # type: ignore
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.LargeBinary(kwargs.get("max_length"))


class UUIDField(FieldFactory, uuid.UUID):
    """Representation of a uuid"""

    field_type = uuid.UUID

    def __new__(cls, **kwargs: Any) -> BaseFieldType:  # type: ignore
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }

        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.UUID()


class ChoiceField(FieldFactory):
    """Representation of an Enum"""

    field_type = enum.Enum

    def __new__(  # type: ignore
        cls,
        choices: Optional[Sequence[Union[tuple[str, str], tuple[str, int]]]] = None,
        **kwargs: dict[str, Any],
    ) -> BaseFieldType:
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        choice_class = kwargs.get("choices")
        if choice_class is None or not isinstance(choice_class, EnumMeta):
            raise FieldDefinitionError("ChoiceField choices must be an Enum")

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> sqlalchemy.Enum:
        choice_class = kwargs.get("choices")
        return sqlalchemy.Enum(choice_class)


class PasswordField(CharField):
    """
    Representation of a Password
    """

    @classmethod
    def get_column_type(self, **kwargs: Any) -> sqlalchemy.String:
        return sqlalchemy.String(length=kwargs.get("max_length"))


class EmailField(CharField):
    field_type = EmailStr

    @classmethod
    def get_column_type(self, **kwargs: Any) -> sqlalchemy.String:
        return sqlalchemy.String(length=kwargs.get("max_length"))


class URLField(CharField):
    @classmethod
    def get_column_type(self, **kwargs: Any) -> sqlalchemy.String:
        return sqlalchemy.String(length=kwargs.get("max_length"))


class IPAddressField(FieldFactory, str):
    field_type = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

    def __new__(  # type: ignore
        cls,
        **kwargs: Any,
    ) -> BaseFieldType:
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }

        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> IPAddress:
        return IPAddress()

    @staticmethod
    def is_native_type(value: str) -> bool:
        return isinstance(value, (ipaddress.IPv4Address, ipaddress.IPv6Address))

    # overwrite
    @classmethod
    def check(cls, field_obj: BaseFieldType, value: Any, original_fn: Any = None) -> Any:
        if cls.is_native_type(value):
            return value

        match_ipv4 = IPV4_REGEX.match(value)
        match_ipv6 = IPV6_REGEX.match(value)

        if not match_ipv4 and not match_ipv6:  # type: ignore
            raise ValueError("Must be a valid IP format.")

        try:
            return ipaddress.ip_address(value)
        except ValueError:
            raise ValueError("Must be a real IP.")  # noqa
