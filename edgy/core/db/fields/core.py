import datetime
import decimal
import enum
import ipaddress
import uuid
import warnings
from collections.abc import Callable, Sequence
from enum import EnumMeta
from functools import cached_property, partial
from re import Pattern
from secrets import compare_digest
from typing import TYPE_CHECKING, Annotated, Any, Optional, Union, cast

import pydantic
import sqlalchemy
from pydantic.networks import AnyUrl, EmailStr, IPvAnyAddress
from sqlalchemy.dialects import oracle

from edgy.core.db.context_vars import CURRENT_INSTANCE, CURRENT_PHASE, EXPLICIT_SPECIFIED_VALUES
from edgy.core.db.fields._internal import IPAddress
from edgy.core.db.fields.base import BaseField, Field
from edgy.core.db.fields.factories import FieldFactory
from edgy.core.db.fields.types import BaseFieldType
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    import zoneinfo

    from edgy.core.db.models.types import BaseModelType


CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


class ComputedField(BaseField):
    def __init__(
        self,
        getter: Union[
            Callable[[BaseFieldType, "BaseModelType", Optional[type["BaseModelType"]]], Any], str
        ],
        setter: Union[Callable[[BaseFieldType, "BaseModelType", Any], None], str, None] = None,
        fallback_getter: Optional[
            Callable[[BaseFieldType, "BaseModelType", Optional[type["BaseModelType"]]], Any]
        ] = None,
        **kwargs: Any,
    ) -> None:
        kwargs["exclude"] = True
        kwargs["null"] = True
        kwargs["primary_key"] = False
        kwargs["field_type"] = kwargs["annotation"] = Any
        self.getter = getter
        self.fallback_getter = fallback_getter
        self.setter = setter
        super().__init__(
            **kwargs,
        )

    @cached_property
    def compute_getter(
        self,
    ) -> Callable[[BaseFieldType, "BaseModelType", Optional[type["BaseModelType"]]], Any]:
        if isinstance(self.getter, str):
            fn = cast(
                Optional[
                    Callable[
                        [BaseFieldType, "BaseModelType", Optional[type["BaseModelType"]]], Any
                    ]
                ],
                getattr(self.owner, self.getter, None),
            )
        else:
            fn = self.getter
        if fn is None and self.fallback_getter is not None:
            fn = self.fallback_getter
        if fn is None:
            raise ValueError(f"No getter found for attribute: {self.getter}.")
        return fn

    @cached_property
    def compute_setter(self) -> Callable[[BaseFieldType, "BaseModelType", Any], None]:
        if isinstance(self.setter, str):
            fn = cast(
                Optional[Callable[[BaseFieldType, "BaseModelType", Any], None]],
                getattr(self.owner, self.setter, None),
            )
        else:
            fn = self.setter
        if fn is None:
            return lambda instance, name, value: None
        return fn

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        return {}

    def clean(
        self,
        name: str,
        value: Any,
        for_query: bool = False,
    ) -> dict[str, Any]:
        return {}

    def __get__(self, instance: "BaseModelType", owner: Any = None) -> Any:
        return self.compute_getter(self, instance, owner)

    def __set__(self, instance: "BaseModelType", value: Any) -> None:
        self.compute_setter(self, instance, value)


class PlaceholderField(FieldFactory):
    """Placeholder field, without db column"""

    def __new__(  # type: ignore
        cls,
        *,
        pydantic_field_type: Any = Any,
        **kwargs: Any,
    ) -> BaseFieldType:
        kwargs.setdefault("exclude", True)
        return super().__new__(cls, pydantic_field_type=pydantic_field_type, **kwargs)

    def clean(
        self,
        name: str,
        value: Any,
        for_query: bool = False,
    ) -> dict[str, Any]:
        return {}

    @classmethod
    def get_pydantic_type(cls, **kwargs: Any) -> Any:
        """Returns the type for pydantic"""
        return kwargs["pydantic_field_type"]


class CharField(FieldFactory, str):
    """String field representation that constructs the Field class and populates the values"""

    field_type = str

    def __new__(  # type: ignore
        cls,
        *,
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
        if max_length is not None and max_length <= 0:
            raise FieldDefinitionError(detail=f"'max_length' is required for {cls.__name__}")

        min_length = kwargs.get("min_length")
        pattern = kwargs.get("regex")

        assert min_length is None or isinstance(min_length, int)
        assert max_length is None or isinstance(max_length, int)
        assert pattern is None or isinstance(pattern, (str, Pattern))

    @classmethod
    def get_column_type(cls, max_length: Optional[int] = None, **kwargs: Any) -> Any:
        return (
            sqlalchemy.Text(collation=kwargs.get("collation"))
            if max_length is None
            else sqlalchemy.String(length=max_length, collation=kwargs.get("collation"))
        )


class TextField(CharField):
    """String representation of a text field which means no max_length required"""

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        kwargs.setdefault("max_length", None)
        super().validate(kwargs)


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
        if (
            increment_on_save == 0
            and kwargs.get("primary_key", False)
            and "autoincrement" not in kwargs
        ):
            warnings.warn(
                (
                    "Not setting autoincrement on an Integer field with `primary_key=True` is deprecated."
                    "We change the default to False in future."
                ),
                DeprecationWarning,
                stacklevel=4,
            )
            kwargs["autoincrement"] = True
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
        max_digits: Optional[int] = None,
        ge: Union[int, float, decimal.Decimal, None] = None,
        gt: Union[int, float, decimal.Decimal, None] = None,
        le: Union[int, float, decimal.Decimal, None] = None,
        lt: Union[int, float, decimal.Decimal, None] = None,
        **kwargs: Any,
    ) -> BaseFieldType:
        # pydantic doesn't support max_digits for float, so rename it
        if max_digits is not None:
            kwargs.setdefault("precision", max_digits)
        del max_digits
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, precision: Optional[int] = None, **kwargs: Any) -> Any:
        if precision is None:
            return sqlalchemy.Float(asdecimal=False)
        return sqlalchemy.Float(precision=precision, asdecimal=False).with_variant(
            oracle.FLOAT(binary_precision=round(precision / 0.30103), asdecimal=False),  # type: ignore
            "oracle",
        )


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


class DurationField(FieldFactory, datetime.timedelta):
    """Representation of a time field"""

    field_type = datetime.timedelta

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Interval()


class TimeField(FieldFactory, datetime.time):
    """Representation of a time field"""

    field_type = datetime.time

    def __new__(cls, with_timezone: bool = False, **kwargs: Any) -> BaseFieldType:  # type: ignore
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
        return sqlalchemy.LargeBinary(length=kwargs.get("max_length"))


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
        return sqlalchemy.Uuid(as_uuid=True, native_uuid=True)


class ChoiceField(FieldFactory):
    """Representation of an Enum"""

    field_type = enum.Enum

    def __new__(  # type: ignore
        cls,
        choices: Optional[Sequence[Union[tuple[str, str], tuple[str, int]]]] = None,
        **kwargs: Any,
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

    def __new__(  # type: ignore
        cls,
        derive_fn: Optional[Callable[[str], str]] = None,
        **kwargs: Any,
    ) -> BaseFieldType:
        kwargs.setdefault("keep_original", derive_fn is not None)
        return super().__new__(cls, derive_fn=derive_fn, **kwargs)

    @classmethod
    def get_embedded_fields(
        cls,
        field_obj: BaseFieldType,
        name: str,
        fields: dict[str, "BaseFieldType"],
        original_fn: Any = None,
    ) -> dict[str, "BaseFieldType"]:
        retdict: dict[str, BaseFieldType] = {}
        # TODO: check if it works in embedded settings or embed_field is required
        if field_obj.keep_original:
            original_pw_name = f"{name}_original"
            if original_pw_name not in fields:
                retdict[original_pw_name] = cast(
                    BaseFieldType,
                    PlaceholderField(
                        pydantic_field_type=str,
                        null=True,
                        exclude=True,
                        read_only=True,
                        name=original_pw_name,
                        owner=field_obj.owner,
                    ),
                )

        return retdict

    @classmethod
    def to_model(
        cls, field_obj: BaseFieldType, field_name: str, value: Any, original_fn: Any = None
    ) -> dict[str, Any]:
        if isinstance(value, (tuple, list)):
            # despite an != should not be a problem here, make sure that strange logics
            # doesn't leak timings of the password
            if not compare_digest(value[0], value[1]):
                raise ValueError("Password doesn't match.")
            else:
                value = value[0]
        retval: dict[str, Any] = {}
        phase = CURRENT_PHASE.get()
        derive_fn = cast(Optional[Callable[[str], str]], field_obj.derive_fn)
        if phase in {"set", "init"} and derive_fn is not None:
            retval[field_name] = derive_fn(value)
            if getattr(field_obj, "keep_original", False):
                retval[f"{field_name}_original"] = value
        else:
            retval[field_name] = value
            # blank after saving or loading
            if phase in {"post_insert", "post_update", "load"} and getattr(
                field_obj, "keep_original", False
            ):
                retval[f"{field_name}_original"] = None

        return retval

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        kwargs.setdefault("secret", True)
        kwargs.setdefault("max_length", 255)
        super().validate(kwargs)


class EmailField(CharField):
    field_type = EmailStr

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        kwargs.setdefault("max_length", 255)
        super().validate(kwargs)

UrlString = Annotated[AnyUrl, pydantic.AfterValidator(lambda v: v if v is None else str(v))]

class URLField(CharField):
    field_type = UrlString  # type: ignore

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        kwargs.setdefault("max_length", 255)
        super().validate(kwargs)


class IPAddressField(FieldFactory, str):
    field_type = IPvAnyAddress

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

        try:
            return ipaddress.ip_address(value)
        except ValueError:
            raise ValueError("Must be a real IP.")  # noqa
