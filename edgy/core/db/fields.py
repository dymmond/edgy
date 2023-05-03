from typing import Any, Optional, Sequence

from edgy.core.db.base import BaseField
from edgy.exceptions import FieldDefinitionError

CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


class FieldFactory:
    """The base for all model fields to be used with EdgeDB"""

    _bases = (BaseField,)
    _is_property: bool = False
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
        is_property = cls._is_property
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
        return None


class StringField(FieldFactory, str):
    """String field representation that constructs the Field class and populates the values"""

    _type = str
    _is_property: bool = True

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
