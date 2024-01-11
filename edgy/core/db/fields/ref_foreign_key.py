import typing
from functools import cached_property
from inspect import isclass
from typing import TYPE_CHECKING, Any, TypeVar

from typing_extensions import get_origin

import edgy
from edgy.core.connection.registry import Registry
from edgy.core.db.constants import CASCADE, RESTRICT
from edgy.core.db.fields._base_fk import BaseField, BaseForeignKey
from edgy.core.terminal import Print
from edgy.exceptions import ModelReferenceError

if TYPE_CHECKING:
    from edgy import Model
    from edgy.core.db.models.model_reference import ModelRef

T = TypeVar("T", bound="Model")


CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]
terminal = Print()


class ForeignKeyFieldFactory:
    def __new__(cls, *args: Any, **kwargs: Any) -> BaseField:  # type: ignore
        cls.validate(**kwargs)

        to: Any = kwargs.pop("to", None)
        null: bool = kwargs.pop("null", False)
        on_update: str = kwargs.pop("on_update", CASCADE)
        on_delete: str = kwargs.pop("on_delete", RESTRICT)
        related_name: str = kwargs.pop("related_name", None)
        comment: str = kwargs.pop("comment", None)
        through: Any = kwargs.pop("through", None)
        owner: Any = kwargs.pop("owner", None)
        server_default: Any = kwargs.pop("server_default", None)
        server_onupdate: Any = kwargs.pop("server_onupdate", None)
        registry: Registry = kwargs.pop("registry", None)
        field_type = list

        namespace = dict(
            __type__=field_type,
            to=to,
            on_update=on_update,
            on_delete=on_delete,
            related_name=related_name,
            annotation=field_type,
            null=null,
            comment=comment,
            owner=owner,
            server_default=server_default,
            server_onupdate=server_onupdate,
            through=through,
            registry=registry,
            column_type=field_type,
            constraints=cls.get_constraints(),
            **kwargs,
        )
        Field = type(cls.__name__, (BaseRefForeignKeyField, BaseField), {})
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


class BaseRefForeignKeyField(BaseForeignKey):
    @cached_property
    def target(self) -> Any:
        """
        The target of the ForeignKey model.
        """
        if not hasattr(self, "_target"):
            if isinstance(self.to.__model__, str):
                self._target = self.registry.models[self.to.__model__]  # type: ignore
            else:
                self._target = self.to.__model__

        self.to.__model__ = self._target
        return self._target


class RefForeignKey(ForeignKeyFieldFactory, list):
    @classmethod
    def is_class_and_subclass(cls, value: typing.Any, _type: typing.Any) -> bool:
        original = get_origin(value)
        if not original and not isclass(value):
            return False

        try:
            if original:
                return original and issubclass(original, _type)
            return issubclass(value, _type)
        except TypeError:
            return False

    def __new__(cls, to: "ModelRef", null: bool = False) -> BaseField:  # type: ignore
        if not cls.is_class_and_subclass(to, edgy.ModelRef):
            raise ModelReferenceError(
                detail="A model reference must be an object of type ModelRef"
            )
        if not hasattr(to, "__model__") or getattr(to, "__model__", None) is None:
            raise ModelReferenceError("'__model__' must bre declared when subclassing ModelRef.")

        kwargs = {
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)
