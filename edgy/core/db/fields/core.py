import copy
import datetime
import decimal
import enum
import ipaddress
import uuid
import warnings
from collections.abc import Callable
from enum import EnumMeta
from re import Pattern
from secrets import compare_digest
from typing import TYPE_CHECKING, Annotated, Any, Optional, Union, cast

import orjson
import pydantic
import sqlalchemy
from monkay import Monkay
from pydantic.networks import AnyUrl, EmailStr, IPvAnyAddress
from sqlalchemy.dialects import oracle

from edgy.core.db.context_vars import CURRENT_PHASE
from edgy.core.db.fields._internal import IPAddress
from edgy.core.db.fields.base import Field
from edgy.core.db.fields.factories import FieldFactory
from edgy.core.db.fields.types import BaseFieldType
from edgy.exceptions import FieldDefinitionError

from .mixins import AutoNowMixin as _AutoNowMixin
from .mixins import IncrementOnSaveBaseField, TimezonedField
from .place_holder_field import PlaceholderField as _PlaceholderField

if TYPE_CHECKING:
    import zoneinfo


CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


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
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        max_length: Optional[int] = kwargs.get("max_length")
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
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
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
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        precision: Optional[int] = kwargs.get("precision")
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
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        # sqlite special we cannot have a big IntegerField as PK
        if kwargs.get("autoincrement"):
            return sqlalchemy.BigInteger().with_variant(sqlalchemy.Integer, "sqlite")
        return sqlalchemy.BigInteger()


class SmallIntegerField(IntegerField):
    """Represents a small integer field"""

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
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
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        return sqlalchemy.Numeric(
            precision=kwargs.get("max_digits"), scale=kwargs.get("decimal_places"), asdecimal=True
        )

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        super().validate(kwargs)

        decimal_places = kwargs.get("decimal_places")
        if decimal_places is None or decimal_places < 0:
            raise FieldDefinitionError("decimal_places are required for DecimalField")


# in python it is not possible to subclass bool. So only use bool for type checking
if TYPE_CHECKING:
    bool_type = bool
else:
    bool_type = int


class BooleanField(FieldFactory, bool_type):
    """Representation of a boolean"""

    field_type = bool

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        return sqlalchemy.Boolean()


class DateTimeField(_AutoNowMixin, datetime.datetime):
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
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        with_timezone: bool = kwargs.get("with_timezone", True)
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


class DateField(_AutoNowMixin, datetime.date):
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
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        return sqlalchemy.Date()


class DurationField(FieldFactory, datetime.timedelta):
    """Representation of a time field"""

    field_type = datetime.timedelta

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
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
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        return sqlalchemy.Time(kwargs.get("with_timezone") or False)


class JSONField(FieldFactory, pydantic.Json):  # type: ignore
    """Representation of a JSONField"""

    field_type = Any

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        return sqlalchemy.JSON()

    @classmethod
    def get_default_value(cls, field_obj: BaseFieldType, original_fn: Any = None) -> Any:
        default = original_fn()
        # copy mutable structures
        if isinstance(default, (list, dict)):
            default = copy.deepcopy(default)
        return default

    @classmethod
    def customize_default_for_server_default(
        cls, field_obj: BaseFieldType, default: Any, original_fn: Any = None
    ) -> Any:
        if callable(default):
            default = default()
        if not isinstance(default, str):
            default = orjson.dumps(default)
        return sqlalchemy.text(":value").bindparams(value=default)


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
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
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
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        return sqlalchemy.Uuid(as_uuid=True, native_uuid=True)


class ChoiceField(FieldFactory):
    """Representation of an Enum"""

    field_type = enum.Enum

    def __new__(  # type: ignore
        cls,
        choices: enum.Enum,
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
    def get_column_type(cls, kwargs: dict[str, Any]) -> sqlalchemy.Enum:
        choice_class = kwargs.get("choices")
        return sqlalchemy.Enum(choice_class)

    @classmethod
    def customize_default_for_server_default(
        cls, field_obj: BaseFieldType, default: Any, original_fn: Any = None
    ) -> Any:
        if callable(default):
            default = default()
        return sqlalchemy.text(":value").bindparams(value=default.name)


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
                    _PlaceholderField(
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
    def get_column_type(cls, kwargs: dict[str, Any]) -> IPAddress:
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


Monkay(
    globals(),
    deprecated_lazy_imports={
        "ComputedField": {
            "path": ".computed_field.ComputedField",
            "reason": "The import path changed.",
            "new_attribute": "edgy.core.db.fields.ComputedField",
        },
        "PlaceholderField": {
            "path": lambda: _PlaceholderField,
            "reason": "The import path changed.",
            "new_attribute": "edgy.core.db.fields.PlaceholderField",
        },
        "AutoNowMixin": {
            "path": lambda: _AutoNowMixin,
            "reason": "We export mixins now from edgy.core.db.fields.mixins.",
            "new_attribute": "edgy.core.db.fields.mixins.AutoNowMixin",
        },
    },
)
