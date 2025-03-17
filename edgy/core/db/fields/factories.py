from collections.abc import Sequence
from functools import lru_cache, partial
from typing import Any, Literal, Union, cast

from edgy.core.db.constants import CASCADE, RESTRICT, SET_NULL
from edgy.core.db.fields.base import Field
from edgy.core.db.fields.types import BaseFieldType
from edgy.exceptions import FieldDefinitionError

CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]

default_methods_overwritable_by_factory: set[str] = {
    key
    for key, attr in BaseFieldType.__dict__.items()
    if callable(attr) and not key.startswith("_")
}
default_methods_overwritable_by_factory.discard("get_column_names")
default_methods_overwritable_by_factory.discard("__init__")

# useful helpers
default_methods_overwritable_by_factory.add("get_default_value")

# extra methods
default_methods_overwritable_by_factory.add("__set__")
default_methods_overwritable_by_factory.add("__get__")
default_methods_overwritable_by_factory.add("modify_input")
default_methods_overwritable_by_factory.add("post_save_callback")
default_methods_overwritable_by_factory.add("post_delete_callback")

# BaseCompositeField
default_methods_overwritable_by_factory.add("translate_name")
default_methods_overwritable_by_factory.add("get_composite_fields")

# Field
default_methods_overwritable_by_factory.add("check")
default_methods_overwritable_by_factory.add("get_column")

# RelationshipField
default_methods_overwritable_by_factory.add("traverse_field")
default_methods_overwritable_by_factory.add("is_cross_db")

# ForeignKey
default_methods_overwritable_by_factory.add("expand_relationship")


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

    field_bases: Sequence[Any] = (Field,)
    field_type: Any = None
    methods_overwritable_by_factory: frozenset[str] = frozenset(
        default_methods_overwritable_by_factory
    )

    def __new__(cls, **kwargs: Any) -> BaseFieldType:
        cls.validate(kwargs)
        return cls.build_field(**kwargs)

    @classmethod
    def build_field(cls, **kwargs: Any) -> BaseFieldType:
        column_type = cls.get_column_type(kwargs)
        pydantic_type = cls.get_pydantic_type(kwargs)
        constraints = cls.get_constraints(kwargs)

        new_field = cls._get_field_cls(cls)

        new_field_obj: BaseFieldType = new_field(  # type: ignore
            field_type=pydantic_type,
            annotation=pydantic_type,
            column_type=column_type,
            constraints=constraints,
            factory=cls,
            **kwargs,
        )
        cls.overwrite_methods(new_field_obj)
        return new_field_obj

    @classmethod
    def overwrite_methods(cls, field_obj: BaseFieldType) -> None:
        """Called in metaclasses"""
        for key in dir(cls):
            if key in cls.methods_overwritable_by_factory and hasattr(cls, key):
                fn = getattr(cls, key)
                original_fn = getattr(field_obj, key, None)
                # use original func, not the wrapper
                if hasattr(fn, "__func__"):
                    fn = fn.__func__

                # fix classmethod, prevent injection of self or class
                setattr(
                    field_obj,
                    key,
                    # .__func__ is a workaround for python < 3.10, python >=3.10 works without
                    staticmethod(partial(fn, cls, field_obj, original_fn=original_fn)).__func__,
                )

    @classmethod
    def repack(cls, field_obj: BaseFieldType) -> None:
        for key in dir(cls):
            if key in cls.methods_overwritable_by_factory and hasattr(cls, key):
                packed_fn = getattr(field_obj, key, None)
                if packed_fn is not None and hasattr(packed_fn, "func"):
                    setattr(
                        field_obj,
                        key,
                        # .__func__ is a workaround for python < 3.10, python >=3.10 works without
                        staticmethod(
                            partial(packed_fn.func, cls, field_obj, **packed_fn.keywords)
                        ).__func__,
                    )

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:  # pragma no cover
        """
        Used to validate if all required parameters on a given field type are set and modify them if needed.
        :param kwargs: dict with all params passed during construction
        :type kwargs: Any
        """

    @classmethod
    def get_constraints(cls, kwargs: dict[str, Any]) -> Sequence[Any]:
        """
        Return the constraints for a column.

        It is passed down as field argument/attribute: `constraints`.
        """
        return []

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns column type for the field, None for Metafields..

        It is passed down as field argument/attribute: `constraints`.
        """
        return None

    @classmethod
    def get_pydantic_type(cls, kwargs: dict[str, Any]) -> Any:
        """Returns the type for pydantic"""
        return cls.field_type

    @staticmethod
    @lru_cache(None)
    def _get_field_cls(cls: "FieldFactory") -> BaseFieldType:
        return cast(BaseFieldType, type(cls.__name__, cast(Any, cls.field_bases), {}))


class ForeignKeyFieldFactory(FieldFactory):
    """The base for all model fields to be used with Edgy"""

    field_type: Any = Any

    def __new__(
        cls,
        *,
        to: Any = None,
        on_update: str = CASCADE,
        on_delete: str = RESTRICT,
        related_name: Union[str, Literal[False]] = "",
        **kwargs: Any,
    ) -> BaseFieldType:
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }
        cls.validate(kwargs)
        # update related name when available
        return cls.build_field(**kwargs)

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """default validation useful for one_to_one and foreign_key"""
        on_update = kwargs.get("on_update", CASCADE)
        on_delete = kwargs.get("on_delete", RESTRICT)
        kwargs.setdefault("null", False)
        null = kwargs["null"]

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

        if related_name:
            kwargs["related_name"] = related_name.lower()
