import typing
from inspect import isclass
from typing import TYPE_CHECKING, Sequence, TypeVar

from typing_extensions import get_origin

import edgy
from edgy.core.db.fields.base import BaseField, BaseForeignKey
from edgy.core.db.fields.core import ForeignKeyFieldFactory
from edgy.core.terminal import Print
from edgy.exceptions import ModelReferenceError

if TYPE_CHECKING:
    from sqlalchemy import Column

    from edgy import Model
    from edgy.core.db.models.model_reference import ModelRef

T = TypeVar("T", bound="Model")


CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]
terminal = Print()


class BaseRefForeignKeyField(BaseForeignKey):
    def get_columns(self, name: str) -> Sequence["Column"]:
        return []


class RefForeignKey(ForeignKeyFieldFactory, list):
    _bases = (BaseRefForeignKeyField,)
    _type = list

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
            raise ModelReferenceError(
                "'__model__' must bre declared when subclassing ModelRef."
            )

        kwargs = {
            **{
                key: value
                for key, value in locals().items()
                if key not in CLASS_DEFAULTS
            },
        }
        return super().__new__(cls, **kwargs)
