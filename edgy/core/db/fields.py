import datetime
import decimal
import enum
import uuid
from typing import Any, Optional, Sequence, Tuple, Union

import pydantic

from edgy.core.db.base import BaseField
from edgy.exceptions import FieldDefinitionError

CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


class FieldFactory:
    """The base for all model fields to be used with EdgeDB"""

    _bases = (BaseField,)
    _property: bool = False
    _is_link: bool = False
    _type: Any = None

    def __new__(cls, *args: Any, **kwargs: Any) -> BaseField:  # type: ignore
        cls.validate(**kwargs)

        default = kwargs.pop("default", None)
        null = kwargs.pop("null", False)
        primary_key = kwargs.pop("primary_key", False)
        autoincrement: bool = kwargs.pop("autoincrement", False)
        unique: bool = kwargs.pop("unique", False)
        index: bool = kwargs.pop("index", False)
        name: str = kwargs.pop("name", None)
        choices: Sequence = set(kwargs.pop("choices", []))

        field_type = cls._type
        is_property = cls._property
        is_link = cls._is_link

        namespace = dict(
            __type__=field_type,
            __property__=is_property,
            __link__=is_link,
            name=name,
            primary_key=primary_key,
            default=default,
            null=null,
            index=index,
            unique=unique,
            autoincrement=autoincrement,
            choices=choices,
            **kwargs,
        )
        Field = type(cls.__name__, cls._bases, {})
        return Field(**namespace)

    @classmethod
    def validate(cls, **kwargs: Any) -> None:  # pragma no cover
        """
        Used to validate if all required parameters on a given field type are set.
        :param kwargs: all params passed during construction
        :type kwargs: Any
        """
        ...

    @classmethod
    def get_column_type(cls, **kwargs) -> Any:
        """Returns the propery column type for the field"""
        return cls._type


class StringField(FieldFactory, str):
    """String field representation that constructs the Field class and populates the values"""

    _type = str
    _property: bool = True

    def __new__(  # type: ignore # noqa CFQ002
        cls,
        *,
        max_length: Optional[int] = 0,
        min_length: Optional[int] = None,
        regex: str = None,
        **kwargs: Any,
    ) -> BaseField:  # type: ignore
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


class TextField(FieldFactory, str):
    """String representation of a text field which means no max_length required"""

    _type = str
    _property: bool = True

    def __new__(cls, **kwargs: Any) -> BaseField:  # type: ignore
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)


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


class FloatField(Number, float):
    """Representation of a int32 and int64"""

    _type = float
    _property: bool = True

    def __new__(
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


class IntegerField(Number, int):
    """
    Integer field factory that construct Field classes and populated their values.
    """

    _type = int
    _property: bool = True

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


class BigIntegerField(IntegerField):
    """Representation of big integer field"""

    ...


class SmallIntegerField(IntegerField):
    """Represents a small integer field"""

    ...


class DecimalField(Number, decimal.Decimal):
    _type = decimal.Decimal
    _property: bool = True

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


class BooleanField(FieldFactory, int):
    """Representation of a boolean"""

    _type = bool
    _property: bool = True

    def __new__(
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


class AutoNowMixin(FieldFactory):
    def __new__(  # type: ignore # noqa CFQ002
        cls,
        *,
        auto_now: Optional[bool] = False,
        auto_now_add: Optional[bool] = False,
        **kwargs: Any,
    ) -> BaseField:  # type: ignore
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
    _property: bool = True

    def __new__(  # type: ignore # noqa CFQ002
        cls,
        *,
        auto_now: Optional[bool] = False,
        auto_now_add: Optional[bool] = False,
        **kwargs: Any,
    ) -> BaseField:  # type: ignore
        if auto_now_add or auto_now:
            kwargs["default"] = datetime.datetime.now

        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)


class DateField(AutoNowMixin, datetime.date):
    """Representation of a date field"""

    _type = datetime.date
    _property: bool = True

    def __new__(  # type: ignore # noqa CFQ002
        cls,
        *,
        auto_now: Optional[bool] = False,
        auto_now_add: Optional[bool] = False,
        **kwargs: Any,
    ) -> BaseField:  # type: ignore
        if auto_now_add or auto_now:
            kwargs["default"] = datetime.datetime.today

        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)


class TimeField(FieldFactory, datetime.time):
    """Representation of a time field"""

    _type = datetime.time
    _property: bool = True

    def __new__(  # type: ignore # noqa CFQ002
        cls, **kwargs: Any
    ) -> BaseField:  # type: ignore
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)


class JSONField(FieldFactory, pydantic.Json):
    """Representation of a JSONField"""

    _type = pydantic.Json
    _property: bool = True


class BinaryField(FieldFactory, bytes):
    """Representation of a binary"""

    _type = bytes
    _property: bool = True

    def __new__(  # type: ignore # noqa CFQ002
        cls, *, max_length: Optional[int] = 0, **kwargs: Any
    ) -> BaseField:  # type: ignore
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


class UUIDField(FieldFactory, uuid.UUID):
    """Representation of a uuid"""

    _type = uuid.UUID
    _property: bool = True

    def __new__(cls, **kwargs: Any) -> BaseField:  # type: ignore # noqa CFQ002
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }

        return super().__new__(cls, **kwargs)


class ChoiceField(FieldFactory):
    """Representation of an Enum"""

    _type = enum.Enum
    _property: bool = True

    def __new__(
        cls, choices: Sequence[Union[Tuple[str, str], Tuple[str, int]]], **kwargs: Any
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)
