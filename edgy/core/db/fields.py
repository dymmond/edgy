import datetime
from typing import Any, Optional, Sequence

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


class FloatField(FieldFactory, float):
    """Representation of a int32 and int64"""

    _type = float
    _property: bool = True

    def __new__(
        cls,
        *,
        mininum: Optional[float] = None,
        maximun: Optional[float] = None,
        multiple_of: Optional[int] = None,
        **kwargs: Any,
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)


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
