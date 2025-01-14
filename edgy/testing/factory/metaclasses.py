from __future__ import annotations

from collections.abc import Callable
from inspect import getmro
from typing import TYPE_CHECKING, Any, ClassVar, cast, no_type_check

import monkay

from edgy.core.db.models import Model
from edgy.testing.exceptions import InvalidModelError
from edgy.utils.compat import is_class_and_subclass

from .fields import FactoryField

if TYPE_CHECKING:
    from faker import Faker

    from edgy.core.connection import Registry

    from .factory import ModelFactory
    from .types import FactoryCallback


# this is not models MetaInfo
class MetaInfo:
    __slots__ = (
        "model",
        "abstract",
        "registry",
        "__edgy_fields__",
        "fields",
        "faker",
        "mappings",
    )
    __ignore_slots__: ClassVar[set[str]] = {"__edgy_fields__", "model", "faker"}
    __edgy_fields__: dict[str, Any]
    default_parameters: dict[str, dict[str, Any] | Callable[[ModelFactory, Faker, dict], Any]]
    model: Model
    abstract: bool
    registry: Registry
    mappings: dict[str, FactoryCallback]

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
        fields: dict[str, dict[str, Any]] = {}
        for base in bases:
            for sub in getmro(base):
                meta: Any = getattr(sub, "meta", None)
                if isinstance(meta, MetaInfo):
                    for name, field in meta.fields.items():
                        if field.no_copy:
                            continue
                        fields.setdefault(name, field.__copy__())

        model: Model | str = getattr(meta_class, "model", None)
        if model is None:
            raise InvalidModelError("Model is required for a factory.") from None

        if isinstance(model, str):
            model = monkay.load(model)

        # Checks if its a valid Edgy model.
        if not is_class_and_subclass(model, Model):
            raise InvalidModelError(f"Class {model.__name__} is not an Edgy model.") from None

        # Assign the meta and the fields of the meta
        meta_info = meta_info_class(
            model.meta,
            meta_class,
            __edgy_fields__=model.meta.fields,
            model=model,
            fields=fields,
            faker=faker,
        )
        for key, value in attrs.items():
            if key == "meta":
                continue
            value: Any = attrs.get(key)
            if isinstance(value, FactoryField):
                field: FactoryField = value.__copy__()
                del attrs[key]
                field.name = key = value.name or key
                fields[key] = field
        for key, edgy_field in model.meta.fields.items():
            if key not in fields:
                field = FactoryField(name=key, field_type=edgy_field, no_copy=True)
                if field.field_type in meta_info.mappings:
                    fields[key] = field
        attrs["meta"] = meta_info

        new_class = cast(type["ModelFactory"], super().__new__(cls, name, bases, attrs, **kwargs))
        for field in fields.values():
            field.owner = new_class
        # validate
        new_class().build()
        return new_class
