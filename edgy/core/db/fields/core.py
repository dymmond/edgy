import copy
import datetime
import decimal
import enum
import ipaddress
import re
import uuid
from enum import EnumMeta
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Optional,
    Pattern,
    Sequence,
    Set,
    Tuple,
    Union,
)

import pydantic
import sqlalchemy
from pydantic import EmailStr, BaseModel

from edgy.core.db.fields._internal import IPAddress
from edgy.core.db.fields._validators import IPV4_REGEX, IPV6_REGEX
from edgy.core.db.fields.base import BaseCompositeField, BaseField
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model

CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


class Field:
    # defines compatibility fallbacks check and get_column

    def check(self, value: Any) -> Any:
        """
        Runs the checks for the fields being validated. Single Column.
        """
        return value

    def clean(self, name: str, value: Any):
        """
        Runs the checks for the fields being validated. Multiple columns possible
        """
        return {name: self.check(value)}

    def get_column(self, name: str) -> Optional[sqlalchemy.Column]:
        """
        Returns the column type of the field being declared.
        """
        constraints = self.get_constraints()
        return sqlalchemy.Column(
            name,
            self.column_type,
            *constraints,
            primary_key=self.primary_key,
            nullable=self.null and not self.primary_key,
            index=self.index,
            unique=self.unique,
            default=self.default,
            comment=self.comment,
            server_default=self.server_default,
            server_onupdate=self.server_onupdate,
        )

    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        column = self.get_column(name)
        if column is None:
            return None
        return [column]


class FieldFactory:
    """The base for all model fields to be used with Edgy"""

    _bases = (
        Field,
        BaseField,
    )
    _type: Any = None

    def __new__(cls, **kwargs: Any) -> BaseField:  # type: ignore
        cls.validate(**kwargs)
        arguments = copy.deepcopy(kwargs)

        default = kwargs.pop("default", None)
        null: bool = kwargs.pop("null", False)
        skip_absorption_check: bool = kwargs.pop("skip_absorption_check", False)
        primary_key: bool = kwargs.pop("primary_key", False)
        autoincrement: bool = kwargs.pop("autoincrement", False)
        unique: bool = kwargs.pop("unique", False)
        index: bool = kwargs.pop("index", False)
        name: str = kwargs.pop("name", None)
        choices: Set[Any] = set(kwargs.pop("choices", []))
        comment: str = kwargs.pop("comment", None)
        owner = kwargs.pop("owner", None)
        server_default = kwargs.pop("server_default", None)
        server_onupdate = kwargs.pop("server_onupdate", None)
        format: str = kwargs.pop("format", None)
        read_only: bool = True if primary_key else kwargs.pop("read_only", False)
        secret: bool = kwargs.pop("secret", False)
        field_type = cls._type

        namespace = dict(
            __type__=field_type,
            annotation=field_type,
            name=name,
            primary_key=primary_key,
            default=default,
            null=null,
            index=index,
            unique=unique,
            autoincrement=autoincrement,
            choices=choices,
            comment=comment,
            owner=owner,
            server_default=server_default,
            server_onupdate=server_onupdate,
            format=format,
            read_only=read_only,
            column_type=cls.get_column_type(**arguments),
            constraints=cls.get_constraints(),
            secret=secret,
            skip_absorption_check=skip_absorption_check,
            **kwargs,
        )
        Field = type(cls.__name__, cls._bases, {})
        return Field(**namespace)  # type: ignore

    @classmethod
    def validate(cls, **kwargs: Any) -> None:  # pragma no cover
        """
        Used to validate if all required parameters on a given field type are set.
        :param kwargs: all params passed during construction
        :type kwargs: Any
        """

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        """Returns the propery column type for the field"""
        return None

    @classmethod
    def get_constraints(cls, **kwargs: Any) -> Any:
        return []


class CompositeField(BaseCompositeField):
    """Aggregates multiple fields into one pseudo field"""

    def __new__(cls, **kwargs: Any) -> BaseField:
        cls.validate(**kwargs)
        return super().__new__(cls)

    def __init__(self, **kwargs: Any):
        name: str = kwargs.pop("name", None)
        owner = kwargs.pop("owner", None)
        read_only: bool = kwargs.pop("read_only", False)
        secret: bool = kwargs.pop("secret", False)
        inner_fields: Sequence[Union[str, Tuple[str, BaseField]]] = kwargs.pop("inner_fields", [])
        field_type = Dict[str, Any]
        self.absorb_existing_fields: bool = kwargs.pop("absorb_existing_fields", False)
        self.model: Optional[BaseModel] = kwargs.pop("model", None)
        self.inner_field_names = []
        self.embedded_field_defs = {}
        for field in inner_fields:
            if isinstance(field, str):
                self.inner_field_names.append(field)
            else:
                self.inner_field_names.append(field[0])
                self.embedded_field_defs[field[0]] = field[1]
                # will be overwritten later
                field[1].owner = owner

        return super().__init__(
            __type__=field_type,
            annotation=field_type,
            name=name,
            primary_key=False,
            null=True,
            index=False,
            exclude=True,
            unique=False,
            autoincrement=False,
            choices=False,
            owner=owner,
            server_default=False,
            server_onupdate=False,
            read_only=read_only,
            column_type=None,
            constraints=[],
            secret=secret,
            **kwargs,
        )

    def __get__(self, instance: "Model", owner: Any = None) -> Dict[str, Any]:
        d = {}
        for key in self.inner_field_names:
            d[key] = getattr(instance, key)
        if self.model is not None:
            return self.model(**d)
        return d

    def __set__(self, instance: "Model", value: Union[Dict, Any]) -> None:
        if isinstance(value, dict):
            for key in self.inner_field_names:
                setattr(instance, key, value[key])
        else:
            for key in self.inner_field_names:
                setattr(instance, key, getattr(value, key))

    def get_embedded_fields(self, name: str, field_mapping: Dict[str, "BaseField"]) -> Dict[str, "BaseField"]:
        if not self.absorb_existing_fields:
            duplicate_fields = set(self.embedded_field_defs.keys()).intersection(field_mapping.keys())
            if duplicate_fields:
                raise ValueError(f"duplicate fields: {', '.join(duplicate_fields)}")
            return dict(self.embedded_field_defs)
        retdict = {}
        for item in self.embedded_field_defs.items():
            if item[0] not in field_mapping:
                retdict[item[0]] = item[1]
            else:
                absorbed_field =field_mapping[item[0]]
                if not issubclass(absorbed_field.field_type, item[1].field_type) and not getattr(absorbed_field, "skip_absorption_check", False):
                    raise ValueError(f"absorption failed: field \"{item[0]}\" handle the type: {absorbed_field.field_type}, required: {item[1].field_type}")
        return retdict

    def get_composite_fields(self) -> Dict[str, BaseField]:
        return {field: self.owner.fields[field] for field in self.inner_field_names}

    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        return []

    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        inner_fields = kwargs.get("inner_fields")
        if inner_fields is not None:
            if not isinstance(inner_fields, Sequence):
                raise FieldDefinitionError("inner_fields must be a Sequence")
            inner_field_names = set()
            for field in inner_fields:
                if isinstance(field, str):
                    if field in inner_field_names:
                        raise FieldDefinitionError(f"duplicate inner field {field}")
                else:
                    if field[0] in inner_field_names:
                        raise FieldDefinitionError(f"duplicate inner field {field}")


class CharField(FieldFactory, str):
    """String field representation that constructs the Field class and populates the values"""

    _type = str

    def __new__(  # type: ignore
        cls,
        *,
        max_length: Optional[int] = 0,
        min_length: Optional[int] = None,
        regex: Union[str, Pattern] = None,
        **kwargs: Any,
    ) -> BaseField:
        if regex is None:
            regex = None
            kwargs["pattern_regex"] = None
        elif isinstance(regex, str):
            regex = regex
            kwargs["pattern_regex"] = re.compile(regex)
        else:
            regex = regex.pattern
            kwargs["pattern_regex"] = regex

        kwargs = {
            **kwargs,
            **{
                key: value
                for key, value in locals().items()
                if key not in CLASS_DEFAULTS
            },
        }

        return super().__new__(cls, **kwargs)

    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        max_length = kwargs.get("max_length", 0)
        if max_length <= 0:
            raise FieldDefinitionError(
                detail=f"'max_length' is required for {cls.__name__}"
            )

        min_length = kwargs.get("min_length")
        pattern = kwargs.get("regex")

        assert min_length is None or isinstance(min_length, int)
        assert max_length is None or isinstance(max_length, int)
        assert pattern is None or isinstance(pattern, (str, Pattern))

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.String(
            length=kwargs.get("max_length"), collation=kwargs.get("collation", None)
        )


class TextField(FieldFactory, str):
    """String representation of a text field which means no max_length required"""

    _type = str

    def __new__(cls, **kwargs: Any) -> BaseField:  # type: ignore
        kwargs = {
            **kwargs,
            **{
                key: value
                for key, value in locals().items()
                if key not in CLASS_DEFAULTS
            },
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Text(collation=kwargs.get("collation", None))


class Number(FieldFactory):
    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        minimum = kwargs.get("minimum", None)
        maximum = kwargs.get("maximum", None)

        if (minimum is not None and maximum is not None) and minimum > maximum:
            raise FieldDefinitionError(
                detail="'minimum' cannot be bigger than 'maximum'"
            )


class IntegerField(Number, int):
    """
    Integer field factory that construct Field classes and populated their values.
    """

    _type = int

    def __new__(  # type: ignore
        cls,
        *,
        minimum: Optional[int] = None,
        maximum: Optional[int] = None,
        multiple_of: Optional[int] = None,
        **kwargs: Any,
    ) -> BaseField:
        autoincrement = kwargs.pop("autoincrement", None)
        autoincrement = (
            autoincrement
            if autoincrement is not None
            else kwargs.get("primary_key", False)
        )
        kwargs = {
            **kwargs,
            **{
                k: v
                for k, v in locals().items()
                if k not in ["cls", "__class__", "kwargs"]
            },
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Integer()


class FloatField(Number, float):
    """Representation of a int32 and int64"""

    _type = float

    def __new__(  # type: ignore
        cls,
        *,
        mininum: Optional[float] = None,
        maximun: Optional[float] = None,
        multiple_of: Optional[int] = None,
        **kwargs: Any,
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{
                key: value
                for key, value in locals().items()
                if key not in CLASS_DEFAULTS
            },
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Float()


class BigIntegerField(IntegerField):
    """Representation of big integer field"""

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.BigInteger()


class SmallIntegerField(IntegerField):
    """Represents a small integer field"""

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.SmallInteger()


class DecimalField(Number, decimal.Decimal):
    _type = decimal.Decimal

    def __new__(  # type: ignore
        cls,
        *,
        minimum: float = None,
        maximum: float = None,
        multiple_of: int = None,
        max_digits: int = None,
        decimal_places: int = None,
        **kwargs: Any,
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{
                k: v
                for k, v in locals().items()
                if k not in ["cls", "__class__", "kwargs"]
            },
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Numeric(
            precision=kwargs.get("max_digits"), scale=kwargs.get("decimal_places")
        )

    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        super().validate(**kwargs)

        max_digits = kwargs.get("max_digits")
        decimal_places = kwargs.get("decimal_places")
        if (
            max_digits is None
            or max_digits < 0
            or decimal_places is None
            or decimal_places < 0
        ):
            raise FieldDefinitionError(
                "max_digits and decimal_places are required for DecimalField"
            )


class BooleanField(FieldFactory, int):
    """Representation of a boolean"""

    _type = bool

    def __new__(  # type: ignore
        cls,
        *,
        default: Optional[bool] = False,
        **kwargs: Any,
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{
                key: value
                for key, value in locals().items()
                if key not in CLASS_DEFAULTS
            },
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Boolean()


class AutoNowMixin(FieldFactory):
    def __new__(  # type: ignore
        cls,
        *,
        auto_now: Optional[bool] = False,
        auto_now_add: Optional[bool] = False,
        **kwargs: Any,
    ) -> BaseField:
        if auto_now_add and auto_now:
            raise FieldDefinitionError(
                "'auto_now' and 'auto_now_add' cannot be both True"
            )

        if auto_now_add or auto_now:
            kwargs["read_only"] = True

        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)


class DateTimeField(AutoNowMixin, datetime.datetime):
    """Representation of a datetime field"""

    _type = datetime.datetime

    def __new__(  # type: ignore
        cls,
        *,
        auto_now: Optional[bool] = False,
        auto_now_add: Optional[bool] = False,
        **kwargs: Any,
    ) -> BaseField:
        if auto_now_add or auto_now:
            kwargs["default"] = datetime.datetime.now

        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.DateTime()


class DateField(AutoNowMixin, datetime.date):
    """Representation of a date field"""

    _type = datetime.date

    def __new__(  # type: ignore
        cls,
        *,
        auto_now: Optional[bool] = False,
        auto_now_add: Optional[bool] = False,
        **kwargs: Any,
    ) -> BaseField:
        if auto_now_add or auto_now:
            kwargs["default"] = datetime.date.today

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

    _type = datetime.time

    def __new__(cls, **kwargs: Any) -> BaseField:  # type: ignore
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Time()


class JSONField(FieldFactory, pydantic.Json):  # type: ignore
    """Representation of a JSONField"""

    _type = Any

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.JSON()


class BinaryField(FieldFactory, bytes):
    """Representation of a binary"""

    _type = bytes

    def __new__(cls, *, max_length: Optional[int] = 0, **kwargs: Any) -> BaseField:  # type: ignore
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        max_length = kwargs.get("max_length", None)
        if max_length <= 0:
            raise FieldDefinitionError(
                detail="Parameter 'max_length' is required for BinaryField"
            )

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.JSON(none_as_null=kwargs.get("sql_nullable", False))


class UUIDField(FieldFactory, uuid.UUID):
    """Representation of a uuid"""

    _type = uuid.UUID

    def __new__(cls, **kwargs: Any) -> BaseField:  # type: ignore
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

    _type = enum.Enum

    def __new__(  # type: ignore
        cls,
        choices: Optional[Sequence[Union[Tuple[str, str], Tuple[str, int]]]] = None,
        **kwargs: Any,
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def validate(cls, **kwargs: Any) -> None:
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
    _type = EmailStr

    @classmethod
    def get_column_type(self, **kwargs: Any) -> sqlalchemy.String:
        return sqlalchemy.String(length=kwargs.get("max_length"))


class URLField(CharField):
    @classmethod
    def get_column_type(self, **kwargs: Any) -> sqlalchemy.String:
        return sqlalchemy.String(length=kwargs.get("max_length"))


class IPAddressField(FieldFactory, str):
    _type = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

    def is_native_type(self, value: str) -> bool:
        return isinstance(value, (ipaddress.IPv4Address, ipaddress.IPv6Address))

    def check(self, value: Any) -> Any:
        if self.is_native_type(value):
            return value

        match_ipv4 = IPV4_REGEX.match(value)
        match_ipv6 = IPV6_REGEX.match(value)

        if not match_ipv4 and not match_ipv6:
            raise ValueError("Must be a valid IP format.")

        try:
            return ipaddress.ip_address(value)
        except ValueError:
            raise ValueError("Must be a real IP.")  # noqa

    def __new__(  # type: ignore
        cls,
        **kwargs: Any,
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{
                key: value
                for key, value in locals().items()
                if key not in CLASS_DEFAULTS
            },
        }

        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> IPAddress:
        return IPAddress()
