from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar, cast, no_type_check

import monkay

from edgy.core.db.models import Model
from edgy.testing.exceptions import InvalidModelError
from edgy.utils.compat import is_class_and_subclass

if TYPE_CHECKING:
    from faker import Faker

    from edgy.core.connection import Registry

    from .factory import ModelFactory


# this is not models MetaInfo
class MetaInfo:
    __slots__ = (
        "model",
        "abstract",
        "registry",
        "__edgy_fields__",
        "default_parameters",
        "faker",
        "mappings",
    )
    __ignore_slots__: ClassVar[set[str]] = {"__edgy_fields__", "model", "faker"}
    __edgy_fields__: dict[str, Any]
    default_parameters: dict[str, dict[str, Any] | Callable[[ModelFactory, Faker, dict], Any]]
    model: Model
    abstract: bool
    registry: Registry
    mappings: dict[str, Callable[[ModelFactory, Faker, dict], Any]]

    def __init__(self, *metas: Any, **kwargs: Any) -> None:
        self.abstract: bool = False
        self.registry: Registry = None
        self.mappings: dict[str, Callable[[ModelFactory, Faker, dict], Any]] = {
            "IntegerField": lambda instance, faker, kwargs: faker.random_int(**kwargs),
            "BigIntegerField": lambda instance, faker, kwargs: faker.random_number(**kwargs),
            "BooleanField": lambda instance, faker, kwargs: faker.boolean(**kwargs),
            "CharField": lambda instance, faker, kwargs: faker.name(**kwargs),
            "DateField": lambda instance, faker, kwargs: faker.date(**kwargs),
            "DateTimeField": lambda instance, faker, kwargs: faker.date_time(**kwargs),
            "DecimalField": lambda instance, faker, kwargs: faker.pyfloat(**kwargs),
            "DurationField": lambda instance, faker, kwargs: faker.time(**kwargs),
            "EmailField": lambda instance, faker, kwargs: faker.email(**kwargs),
            "FloatField": lambda instance, faker, kwargs: faker.pyfloat(**kwargs),
            "IPAddressField": lambda instance, faker, kwargs: faker.ipv4(**kwargs),
            "PasswordField": lambda instance, faker, kwargs: faker.ipv4(**kwargs),
            "SmallIntegerField": lambda instance, faker, kwargs: faker.random_int(**kwargs),
            "TextField": lambda instance, faker, kwargs: faker.text(**kwargs),
            "TimeField": lambda instance, faker, kwargs: faker.time(**kwargs),
            "UUIDField": lambda instance, faker, kwargs: faker.uuid4(**kwargs),
        }
        for meta in metas:
            for slot in self.__slots__:
                if slot in self.__ignore_slots__:
                    continue
                value = getattr(meta, slot, None)
                if value is not None:
                    if slot == "mappings":
                        value = value.copy()
                    setattr(self, slot, value)
        for name, value in kwargs.items():
            setattr(self, name, value)


class ModelFactoryMeta(type):
    @no_type_check
    def __new__(
        cls,
        name,
        bases,
        attrs: dict[str, Any],
        meta_info_class: type[MetaInfo] = MetaInfo,
        **kwargs: Any,
    ):
        # cls: Model = super().__new__(mcls, name, bases, attrs)
        try:
            from faker import Faker
        except ImportError:
            raise ImportError("Faker is required for the factory.") from None
        faker = Faker()

        model_class = super().__new__

        parents = [parent for parent in bases if isinstance(parent, ModelFactoryMeta)]
        if not parents:
            return model_class(cls, name, bases, attrs)
        meta_class = attrs.pop("Meta", None)
        default_parameters: dict[str, dict[str, Any]] = {}

        model: Model | str = getattr(meta_class, "model", None)
        if model is None:
            raise InvalidModelError("Model is required for a factory.") from None

        if isinstance(model, str):
            model = monkay.load(model)
        for key in model.meta.fields:
            if key == "meta":
                continue
            value: Any = attrs.pop(key, None)
            if isinstance(value, dict) or callable(value):
                default_parameter: dict[str, Any] | Callable[[ModelFactory, Faker, dict], Any] = (
                    value
                )
            else:
                default_parameter = {}
            default_parameters[key] = default_parameter

        # Checks if its a valid Edgy model.
        if not is_class_and_subclass(model, Model):
            raise InvalidModelError(f"Class {model.__name__} is not an Edgy model.") from None

        # Assign the meta and the fields of the meta
        meta_info = meta_info_class(
            model.meta,
            meta_class,
            __edgy_fields__=model.meta.fields,
            model=model,
            default_parameters=default_parameters,
            faker=faker,
        )
        attrs["meta"] = meta_info

        new_class = cast(type["ModelFactory"], super().__new__(cls, name, bases, attrs, **kwargs))
        # validate
        new_class().build()
        return new_class
