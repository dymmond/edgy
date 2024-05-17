import copy
import datetime
import decimal
import enum
import ipaddress
import re
import uuid
from enum import EnumMeta
from functools import lru_cache
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Pattern,
    Sequence,
    Set,
    Tuple,
    Union,
    cast,
)

import pydantic
import sqlalchemy
from pydantic import BaseModel, EmailStr

from edgy.core.db.fields._internal import IPAddress
from edgy.core.db.fields._validators import IPV4_REGEX, IPV6_REGEX
from edgy.core.db.fields.base import BaseCompositeField, BaseField
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model

CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


def _removeprefix(text: str, prefix: str) -> str:
    # TODO: replace with removeprefix when python3.9 is minimum
    if text.startswith(prefix):
        return text[len(prefix) :]
    else:
        return text


class Field:
    # defines compatibility fallbacks check and get_column

    def check(self, value: Any) -> Any:
        """
        Runs the checks for the fields being validated. Single Column.
        """
        return value

    def clean(self, name: str, value: Any) -> Dict[str, Any]:
        """
        Runs the checks for the fields being validated. Multiple columns possible
        """
        return {name: self.check(value)}

    def get_column(self, name: str) -> Optional[sqlalchemy.Column]:
        """
        Return a single column for the field declared. Return None for meta fields.
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
            return []
        return [column]

    @classmethod
    def get_constraints(cls, **kwargs: Any) -> Any:
        return []


class FieldFactoryMeta(type):
    def __instancecheck__(self, instance: Any) -> bool:
        return super().__instancecheck__(instance) or isinstance(
            instance, self._get_field_cls(self)
        )

    def __subclasscheck__(self, subclass: Any) -> bool:
        return super().__subclasscheck__(subclass) or issubclass(
            subclass, self._get_field_cls(self)
        )


class FieldFactory(metaclass=FieldFactoryMeta):
    """The base for all model fields to be used with Edgy"""

    _bases: Sequence[Any] = (Field, BaseField)
    _type: Any = None

    def __new__(cls, **kwargs: Any) -> BaseField:
        cls.validate(**kwargs)
        field_type = cls._type
        column_type = cls.get_column_type(**kwargs)
        default: None = kwargs.pop("default", None)
        server_default: None = kwargs.pop("server_default", None)

        new_field = cls._get_field_cls(cls)
        return new_field(  # type: ignore
            __type__=field_type,
            annotation=field_type,
            column_type=column_type,
            default=default,
            server_default=server_default,
            **kwargs,
        )

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

    @staticmethod
    @lru_cache(None)
    def _get_field_cls(cls: "FieldFactory") -> BaseField:
        return cast(BaseField, type(cls.__name__, cast(Any, cls._bases), {}))


class ConcreteCompositeField:
    """
    Conrete, internal implementation of the CompositeField
    """

    def __init__(self, **kwargs: Any):
        owner = kwargs.pop("owner", None)
        inner_fields: Sequence[Union[str, Tuple[str, BaseField]]] = kwargs.pop(
            "inner_fields", []
        )
        self.absorb_existing_fields: bool = kwargs.pop("absorb_existing_fields", False)
        self.model: Optional[BaseModel] = kwargs.pop("model", None)
        self.inner_field_names: List[str] = []
        self.embedded_field_defs: Dict[str, BaseField] = {}
        self.prefix_embedded: str = kwargs.pop("prefix_embedded", "")
        for field in inner_fields:
            if isinstance(field, str):
                self.inner_field_names.append(field)
            else:
                field_name = f"{self.prefix_embedded}{field[0]}"
                field_def = copy.deepcopy(field[1])
                self.inner_field_names.append(field_name)
                self.embedded_field_defs[field_name] = field_def
                # will be overwritten later
                field_def.owner = owner

        return super().__init__(  # type: ignore
            name=None,
            primary_key=False,
            autoincrement=False,
            index=False,
            exclude=True,
            null=True,
            unique=False,
            choices=False,
            owner=owner,
            server_onupdate=None,
            constraints=[],
            **kwargs,
        )

    def translate_name(self, name: str) -> str:
        if self.prefix_embedded and name in self.embedded_field_defs:
            # PYTHON 3.8 compatibility
            return _removeprefix(name, self.prefix_embedded)
        return name

    def __get__(
        self, instance: "Model", owner: Any = None
    ) -> Union[Dict[str, Any], Any]:
        d = {}
        for key in self.inner_field_names:
            translated_name = self.translate_name(key)
            d[translated_name] = getattr(instance, key)
        if self.model is not None:
            return self.model(**d)  # type: ignore
        return d

    def __set__(self, instance: "Model", value: Union[Dict, Any]) -> None:
        if isinstance(value, dict):
            for key in self.inner_field_names:
                translated_name = self.translate_name(key)
                setattr(instance, key, value[translated_name])
        else:
            for key in self.inner_field_names:
                translated_name = self.translate_name(key)
                setattr(instance, key, getattr(value, translated_name))

    def get_embedded_fields(
        self, name: str, field_mapping: Dict[str, "BaseField"]
    ) -> Dict[str, "BaseField"]:
        if not self.absorb_existing_fields:
            duplicate_fields = set(self.embedded_field_defs.keys()).intersection(
                field_mapping.keys()
            )
            if duplicate_fields:
                raise ValueError(f"duplicate fields: {', '.join(duplicate_fields)}")
            return dict(self.embedded_field_defs)
        retdict = {}
        for item in self.embedded_field_defs.items():
            if item[0] not in field_mapping:
                retdict[item[0]] = item[1]
            else:
                absorbed_field = field_mapping[item[0]]
                if not getattr(
                    absorbed_field, "skip_absorption_check", False
                ) and not issubclass(absorbed_field.field_type, item[1].field_type):
                    raise ValueError(
                        f'absorption failed: field "{item[0]}" handle the type: {absorbed_field.field_type}, required: {item[1].field_type}'
                    )
        return retdict

    def get_composite_fields(self) -> Dict[str, BaseField]:
        return {field: self.owner.fields[field] for field in self.inner_field_names}

    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        return []


class CompositeField(FieldFactory):
    """
    Meta field that aggregates multiple fields in a pseudo field
    """

    _type = Union[Dict[str, Any], object]
    _bases = (ConcreteCompositeField, BaseCompositeField)

    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        inner_fields = kwargs.get("inner_fields")
        if inner_fields is not None:
            if not isinstance(inner_fields, Sequence):
                raise FieldDefinitionError("inner_fields must be a Sequence")
            inner_field_names: Set[str] = set()
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
