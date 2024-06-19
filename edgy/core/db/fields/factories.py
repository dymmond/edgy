from functools import lru_cache
from typing import Any, Literal, Sequence, Union, cast

from edgy.core.db.constants import CASCADE, RESTRICT, SET_NULL
from edgy.core.db.fields.base import BaseField, Field
from edgy.exceptions import FieldDefinitionError

CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


class FieldFactoryMeta(type):
    def __instancecheck__(self, instance: Any) -> bool:
        return super().__instancecheck__(instance) or isinstance(instance, self._get_field_cls(self))

    def __subclasscheck__(self, subclass: Any) -> bool:
        return super().__subclasscheck__(subclass) or issubclass(subclass, self._get_field_cls(self))


class FieldFactory(metaclass=FieldFactoryMeta):
    """The base for all model fields to be used with Edgy"""

    _bases: Sequence[Any] = (Field,)
    _type: Any = None

    def __new__(cls, **kwargs: Any) -> BaseField:
        cls.validate(**kwargs)
        return cls.build_field(**kwargs)

    @classmethod
    def build_field(cls, **kwargs: Any) -> BaseField:
        column_type = cls.get_column_type(**kwargs)
        pydantic_type = cls.get_pydantic_type(**kwargs)
        constraints = cls.get_constraints(**kwargs)
        default: None = kwargs.pop("default", None)
        server_default: None = kwargs.pop("server_default", None)

        new_field = cls._get_field_cls(cls)
        return new_field(  # type: ignore
            __type__=pydantic_type,
            annotation=pydantic_type,
            column_type=column_type,
            default=default,
            server_default=server_default,
            constraints=constraints,
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
    def get_constraints(cls, **kwargs: Any) -> Sequence[Any]:
        """Returns the propery column type for the field, None for Metafields"""
        return []

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        """Returns the propery column type for the field, None for Metafields"""
        return None

    @classmethod
    def get_pydantic_type(cls, **kwargs: Any) -> Any:
        """Returns the type for pydantic"""
        return cls._type

    @staticmethod
    @lru_cache(None)
    def _get_field_cls(cls: "FieldFactory") -> BaseField:
        return cast(BaseField, type(cls.__name__, cast(Any, cls._bases), {}))


class ForeignKeyFieldFactory(FieldFactory):
    """The base for all model fields to be used with Edgy"""

    _type: Any = Any

    def __new__(
        cls,
        *,
        to: Any = None,
        null: bool = False,
        on_update: str = CASCADE,
        on_delete: str = RESTRICT,
        related_name: Union[str, Literal[False]] = "",
        server_onupdate: Any = None,
        default: Any = None,
        server_default: Any = None,
        **kwargs: Any,
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }

        cls.validate(**kwargs)
        # update related name when available
        if related_name:
            kwargs["related_name"] = related_name.lower()
        return cls.build_field(**kwargs)

    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        """default validation useful for one_to_one and foreign_key"""
        on_delete = kwargs.get("on_delete", CASCADE)
        on_update = kwargs.get("on_update", RESTRICT)
        null = kwargs.get("null", False)

        if on_delete is None:
            raise FieldDefinitionError("on_delete must not be null.")

        if on_delete == SET_NULL and not null:
            raise FieldDefinitionError("When SET_NULL is enabled, null must be True.")

        if on_update and (on_update == SET_NULL and not null):
            raise FieldDefinitionError("When SET_NULL is enabled, null must be True.")
        related_name = kwargs.get("related_name", "")

        # tolerate None and False
        if related_name and not isinstance(related_name, str):
            raise FieldDefinitionError("related_name must be a string.")
