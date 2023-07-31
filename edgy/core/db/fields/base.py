import datetime
import decimal
import enum
import uuid
from enum import EnumMeta
from typing import Any, Optional, Sequence, Set, Tuple, Union

import pydantic
import sqlalchemy

from edgy.core.db.base import BaseField
from edgy.exceptions import FieldDefinitionError

CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


class FieldFactory:
    """The base for all model fields to be used with Edgy"""

    _bases = (BaseField,)
    _type: Any = None

    def __new__(cls, *args: Any, **kwargs: Any) -> BaseField:  # type: ignore
        cls.validate(**kwargs)

        default = kwargs.pop("default", None)
        null: bool = kwargs.pop("null", False)
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


class CharField(FieldFactory, str):
    """String field representation that constructs the Field class and populates the values"""

    _type = str

    def __new__(  # type: ignore
        cls,
        *,
        max_length: Optional[int] = 0,
        min_length: Optional[int] = None,
        regex: str = None,  # type: ignore
        **kwargs: Any,
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }

        return super().__new__(cls, **kwargs)

    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        max_length = kwargs.get("max_length", 0)
        if max_length <= 0:
            raise FieldDefinitionError(detail=f"'max_length' is required for {cls.__name__}")

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.String(length=kwargs.get("max_length"))


class TextField(FieldFactory, str):
    """String representation of a text field which means no max_length required"""

    _type = str

    def __new__(cls, **kwargs: Any) -> BaseField:  # type: ignore
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Text()


class Number(FieldFactory):
    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        minimum = kwargs.get("minimum", None)
        maximum = kwargs.get("maximum", None)
        exclusive_minimum = kwargs.get("exclusive_minimum", None)
        exclusive_maximum = kwargs.get("exclusive_maximum", None)

        if (minimum is not None and maximum is not None) and minimum > maximum:
            raise FieldDefinitionError(detail="'minimum' cannot be bigger than 'maximum'")

        if (
            exclusive_maximum is not None and exclusive_maximum is not None
        ) and exclusive_minimum > exclusive_maximum:
            raise FieldDefinitionError(
                detail="'exclusive_minimum' cannot be bigger than 'exclusive_maximum'"
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
        exclusive_minimum: Optional[float] = None,
        exclusive_maximum: Optional[float] = None,
        multiple_of: Optional[int] = None,
        **kwargs: Any,
    ) -> BaseField:
        autoincrement = kwargs.pop("autoincrement", None)
        autoincrement = (
            autoincrement if autoincrement is not None else kwargs.get("primary_key", False)
        )
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in ["cls", "__class__", "kwargs"]},
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
        exclusive_minimum: Optional[float] = None,
        exclusive_maximum: Optional[float] = None,
        multiple_of: Optional[int] = None,
        **kwargs: Any,
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
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
        minimum: Optional[int] = None,
        maximum: Optional[int] = None,
        exclusive_minimum: Optional[float] = None,
        exclusive_maximum: Optional[float] = None,
        multiple_of: Optional[int] = None,
        precision: Optional[int] = None,
        max_digits: Optional[int] = None,
        decimal_places: Optional[int] = None,
        **kwargs: Any,
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in ["cls", "__class__", "kwargs"]},
        }
        if kwargs.get("max_digits"):
            kwargs["precision"] = kwargs["max_digits"]
        elif kwargs.get("precision"):
            kwargs["max_digits"] = kwargs["precision"]

        return super().__new__(cls, **kwargs)

    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        super().validate(**kwargs)

        precision = kwargs.get("precision")
        if precision is None or precision < 0:
            raise FieldDefinitionError(
                "'max_digits' and 'precision' are required for DecimalField"
            )

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Numeric(
            precision=kwargs.get("max_digits"), scale=kwargs.get("decimal_places")
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
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
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
            raise FieldDefinitionError("'auto_now' and 'auto_now_add' cannot be both True")
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
            kwargs["default"] = datetime.datetime.today

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

    _type = pydantic.Json

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
            raise FieldDefinitionError(detail="Parameter 'max_length' is required for BinaryField")

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
        if choice_class is None and not isinstance(choice_class, EnumMeta):
            raise FieldDefinitionError("ChoiceField choices must be an Enum")

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Enum(kwargs.get("choices", ()))


class PasswordField(CharField):
    """
    Representation of a Password
    """

    @classmethod
    def get_column_type(self, **kwargs: Any) -> sqlalchemy.String:
        return sqlalchemy.String(length=kwargs.get("max_length"))


class EmailField(CharField):
    @classmethod
    def get_column_type(self, **kwargs: Any) -> sqlalchemy.String:
        return sqlalchemy.String(length=self.validator.max_length)  # type: ignore


class URLField(CharField):
    @classmethod
    def get_column_type(self, **kwargs: Any) -> sqlalchemy.String:
        return sqlalchemy.String(length=self.validator.max_length)  # type: ignore
