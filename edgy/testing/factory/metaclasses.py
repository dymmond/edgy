from __future__ import annotations

from collections.abc import Callable
from inspect import getmro, isclass
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

import monkay
from pydantic import ValidationError

from edgy.core.db.models import Model
from edgy.core.terminal import Print
from edgy.testing.exceptions import InvalidModelError
from edgy.utils.compat import is_class_and_subclass

from .fields import FactoryField
from .utils import edgy_field_param_extractor

if TYPE_CHECKING:
    import enum

    from faker import Faker

    from edgy.core.connection import Registry

    from .base import ModelFactory
    from .types import FactoryCallback


terminal = Print()


def ChoiceField_callback(field: FactoryField, faker: Faker, kwargs: dict[str, Any]) -> Any:
    choices: enum.Enum = field.owner.meta.model.meta.fields[field.name].choices

    return faker.enum(choices)


def ForeignKey_callback(field: FactoryField, faker: Faker, kwargs: dict[str, Any]) -> Any:
    from .base import ModelFactory

    class ForeignKeyFactory(ModelFactory):
        class Meta:
            model = field.owner.meta.model.meta.fields[field.name].target

    factory = ForeignKeyFactory()

    # arm callback
    field.callback = lambda field, faker, k: factory.build(**k)
    return field.callback(field, faker, kwargs)


def ManyToManyField_callback(field: FactoryField, faker: Faker, kwargs: dict[str, Any]) -> Any:
    from .base import ModelFactory

    class ManyToManyFieldFactory(ModelFactory):
        class Meta:
            model = field.owner.meta.model.meta.fields[field.name].target

    factory = ManyToManyFieldFactory()

    field.callback = lambda field, faker, k: [
        factory.build(parameters=k.get("parameters"), overwrites=k.get("overwrites"))
        for i in range(faker.random_int(min=k.get("min", 0), max=k.get("max", 100)))
    ]
    return field.callback(field, faker, kwargs)


def RefForeignKey_callback(field: FactoryField, faker: Faker, kwargs: dict[str, Any]) -> Any:
    from .base import ModelFactory

    class RefForeignKeyFactory(ModelFactory):
        class Meta:
            model = field.owner.meta.model.meta.fields[field.name].to

    factory = RefForeignKeyFactory()

    field.callback = lambda field, faker, k: [
        factory.build(parameters=k.get("parameters"), overwrites=kwargs.get("overwrites"))
        for i in range(faker.random_int(min=k.get("min", 0), max=k.get("max", 100)))
    ]
    return field.callback(field, faker, kwargs)


DEFAULT_MAPPING: dict[str, FactoryCallback | None] = {
    "IntegerField": edgy_field_param_extractor(
        "random_int", remapping={"gt": ("min", lambda x: x - 1), "lt": ("max", lambda x: x + 1)}
    ),
    "BigIntegerField": edgy_field_param_extractor(
        "random_number", remapping={"gt": ("min", lambda x: x - 1), "lt": ("max", lambda x: x + 1)}
    ),
    "SmallIntegerField": edgy_field_param_extractor(
        "random_int", remapping={"gt": ("min", lambda x: x - 1), "lt": ("max", lambda x: x + 1)}
    ),
    "DecimalField": edgy_field_param_extractor(
        "pydecimal",
        remapping={
            # TODO: find better definition
            "gt": ("min", lambda x: x - 0.0000000001),
            "lt": ("max", lambda x: x + 0.0000000001),
        },
    ),
    "FloatField": edgy_field_param_extractor(
        "pyfloat",
        remapping={
            # TODO: find better definition
            "gt": ("min", lambda x: x - 0.0000000001),
            "lt": ("max", lambda x: x + 0.0000000001),
        },
    ),
    "BooleanField": edgy_field_param_extractor("boolean"),
    "URLField": edgy_field_param_extractor("uri"),
    "ImageField": edgy_field_param_extractor(
        "binary", remapping={"max_length": ("length", lambda x: x)}
    ),
    "FileField": edgy_field_param_extractor("binary"),
    "ChoiceField": ChoiceField_callback,
    "CharField": edgy_field_param_extractor("name"),
    "DateField": edgy_field_param_extractor("date"),
    "DateTimeField": edgy_field_param_extractor("date_time"),
    "DurationField": edgy_field_param_extractor("time"),
    "EmailField": edgy_field_param_extractor("email"),
    "BinaryField": edgy_field_param_extractor(
        "binary", remapping={"max_length": ("length", lambda x: x)}
    ),
    "IPAddressField": edgy_field_param_extractor("ipv4"),
    "PasswordField": edgy_field_param_extractor("ipv4"),
    "TextField": edgy_field_param_extractor("text"),
    "TimeField": edgy_field_param_extractor("time"),
    "UUIDField": edgy_field_param_extractor("uuid4"),
    "JSONField": edgy_field_param_extractor("json"),
    "ForeignKey": ForeignKey_callback,
    "OneToOneField": ForeignKey_callback,
    "OneToOne": ForeignKey_callback,
    "ManyToManyField": ManyToManyField_callback,
    "ManyToMany": ManyToManyField_callback,
    "RefForeignKey": RefForeignKey_callback,
    # special fields without mapping, they need a custom user defined logic
    "CompositeField": None,
    "ComputedField": None,
    "PKField": None,
    # can't hold a value
    "ExcludeField": None,
    # private. Used by other fields to save a private value.
    "PlaceholderField": None,
}


# this is not models MetaInfo
class MetaInfo:
    __slots__ = (
        "model",
        "abstract",
        "registry",
        "fields",
        "faker",
        "mappings",
    )
    __ignore_slots__: ClassVar[set[str]] = {"fields", "model", "faker", "mappings"}
    __edgy_fields__: dict[str, Any]
    default_parameters: dict[str, dict[str, Any] | Callable[[ModelFactory, Faker, dict], Any]]
    model: type[Model]
    abstract: bool
    registry: Registry
    mappings: dict[str, FactoryCallback | None]

    def __init__(self, *metas: Any, **kwargs: Any) -> None:
        self.abstract: bool = False
        self.registry: Registry = None
        self.mappings: dict[str, FactoryCallback | None] = {}
        for meta in metas:
            for slot in self.__slots__:
                if slot in self.__ignore_slots__:
                    continue
                value = getattr(meta, slot, None)
                if value is not None:
                    setattr(self, slot, value)
        for name, value in kwargs.items():
            setattr(self, name, value)


class ModelFactoryMeta(type):
    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        attrs: dict[str, Any],
        meta_info_class: type[MetaInfo] = MetaInfo,
        model_validation: Literal["none", "warn", "error", "pedantic"] = "warn",
        **kwargs: Any,
    ) -> type[ModelFactory]:
        # has parents
        if not any(True for parent in bases if isinstance(parent, ModelFactoryMeta)):
            return super().__new__(cls, name, bases, attrs, **kwargs)  # type: ignore
        try:
            from faker import Faker
        except ImportError:
            raise ImportError("Faker is required for the factory.") from None
        faker = Faker()
        meta_class: Any = attrs.pop("Meta", None)
        fields: dict[str, FactoryField] = {}
        mappings: dict[str, FactoryCallback] = {}
        # of the current Meta
        current_mapping: dict[str, FactoryCallback | None] = (
            getattr(meta_class, "mappings", None) or {}
        )
        for name, mapping in current_mapping:
            mappings.setdefault(name, mapping)
        for base in bases:
            for sub in getmro(base):
                meta: Any = getattr(sub, "meta", None)
                if isinstance(meta, MetaInfo):
                    for name, mapping in meta.mappings.items():
                        mappings.setdefault(name, mapping)
                    for name, field in meta.fields.items():
                        if field.no_copy:
                            continue
                        if not field.callback and field.get_field_type() not in mappings:
                            terminal.write_warning(
                                f'Mapping for field type: "{field.get_field_type()}" not found. Skip field: "{field.name}".'
                                f'\nDiffering ModelFactory field name: "{field.original_name}".'
                                if field.original_name != field.name
                                else ""
                            )
                        else:
                            fields.setdefault(name, field.__copy__())

        # now add the default mapping
        for name, mapping in DEFAULT_MAPPING.items():
            mappings.setdefault(name, mapping)

        db_model: type[Model] | str | None = getattr(meta_class, "model", None)
        if db_model is None:
            raise InvalidModelError("Model is required for a factory.") from None

        if isinstance(db_model, str):
            db_model = cast(type["Model"], monkay.load(db_model))

        # Checks if its a valid Edgy model.
        if not is_class_and_subclass(db_model, Model):
            db_model_name = db_model.__name__ if isclass(db_model) else type(db_model.__name__)
            raise InvalidModelError(f"Class {db_model_name} is not an Edgy model.") from None

        # Assign the meta and the fields of the meta
        meta_info = meta_info_class(
            db_model.meta, meta_class, model=db_model, faker=faker, mappings=mappings
        )
        # update fields
        for key in list(attrs.keys()):
            if key == "meta":
                continue
            value: Any = attrs.get(key)
            if isinstance(value, FactoryField):
                value.original_name = key
                del attrs[key]
                value.name = name = value.name or key
                if (
                    not value.callback
                    and value.get_field_type(db_model_meta=db_model.meta) not in mappings
                ):
                    terminal.write_warning(
                        f'Mapping for field type: "{value.get_field_type(db_model_meta=db_model.meta)}" not found. Skip field: "{value.name}".'
                        f'\nDiffering ModelFactory field name: "{value.original_name}".'
                        if value.original_name != value.name
                        else ""
                    )
                else:
                    fields[name] = value
        for db_field_name in db_model.meta.fields:
            if db_field_name not in fields:
                field = FactoryField(name=db_field_name, no_copy=True)
                field.original_name = db_field_name
                field_type = field.get_field_type(db_model_meta=db_model.meta)
                if field_type not in meta_info.mappings:
                    terminal.write_warning(
                        f'Mapping for field type: "{field_type}" not found. Skip field: "{field.name}".'
                        f'\nDiffering ModelFactory field name: "{field.original_name}".'
                        if field.original_name != field.name
                        else ""
                    )
                else:
                    mapping_result = meta_info.mappings.get(field_type)
                    # ignore None, which can be used to exclude fields
                    if mapping_result:
                        fields[field.name] = field

        meta_info.fields = fields
        attrs["meta"] = meta_info

        new_class = cast(type["ModelFactory"], super().__new__(cls, name, bases, attrs, **kwargs))
        # set owner
        for field in fields.values():
            field.owner = new_class
        # validate
        if model_validation != "none":
            try:
                new_class().build(save_after=False)
            except ValidationError as exc:
                if model_validation == "pedantic":
                    raise exc
            except Exception as exc:
                if model_validation == "error" or model_validation == "pedantic":
                    raise exc
                terminal.write_warning(f'Could not build a sample model instance: "{exc!r}".')
        return new_class
