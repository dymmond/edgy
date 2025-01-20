from __future__ import annotations

from typing import TYPE_CHECKING, Any

from edgy.core.files import File

from .utils import edgy_field_param_extractor

if TYPE_CHECKING:
    import enum

    from faker import Faker

    from .fields import FactoryField
    from .types import FactoryCallback


def ChoiceField_callback(field: FactoryField, faker: Faker, parameters: dict[str, Any]) -> Any:
    choices: type[enum.Enum] = field.owner.meta.model.meta.fields[field.name].choices

    return faker.enum(choices)


def ForeignKey_callback(field: FactoryField, faker: Faker, parameters: dict[str, Any]) -> Any:
    from .base import ModelFactory

    edgy_field = field.owner.meta.model.meta.fields[field.name]

    class ForeignKeyFactory(ModelFactory):
        class Meta:
            model = edgy_field.target

    factory = ForeignKeyFactory()

    # arm callback
    def callback(field: FactoryField, faker: Faker, k: dict[str, Any]) -> Any:
        k["exclude"] = {*(k.get("exclude") or []), edgy_field.related_name}  # type: ignore
        k["exclude"].discard(False)
        return factory.build(faker=faker, **k)

    field.callback = callback
    return field.callback(field, faker, parameters)


def ManyToManyField_callback(field: FactoryField, faker: Faker, parameters: dict[str, Any]) -> Any:
    from .base import ModelFactory

    edgy_field = field.owner.meta.model.meta.fields[field.name]

    class ManyToManyFieldFactory(ModelFactory):
        class Meta:
            model = edgy_field.target

    factory = ManyToManyFieldFactory()

    # arm callback
    def callback(field: FactoryField, faker: Faker, k: dict[str, Any]) -> Any:
        k["exclude"] = {*(k.get("exclude") or []), edgy_field.related_name}  # type: ignore
        k["exclude"].discard(False)
        min_value = k.pop("min", 0)
        max_value = k.pop("max", 100)
        return [
            factory.build(faker=faker, **k)
            for i in range(faker.random_int(min=min_value, max=max_value))
        ]

    field.callback = callback

    return field.callback(field, faker, parameters)


def RefForeignKey_callback(field: FactoryField, faker: Faker, parameters: dict[str, Any]) -> Any:
    from .base import ModelFactory

    edgy_model_meta = field.owner.meta.model.meta
    model_ref = edgy_model_meta.fields[field.name].to
    edgy_field = edgy_model_meta.fields[model_ref.__related_name__]

    class RefForeignKeyFactory(ModelFactory):
        class Meta:
            model = edgy_field.target

    factory = RefForeignKeyFactory()
    model_ref_exclude: set[str] = set()
    model_fields = model_ref.model_fields
    for field_name in edgy_model_meta.fields:
        if field_name not in model_fields:
            model_ref_exclude.add(field_name)

    def callback(field: FactoryField, faker: Faker, k: dict[str, Any]) -> Any:
        k["exclude"] = {*(k.get("exclude") or []), edgy_field.related_name}  # type: ignore
        k["exclude"].discard(False)
        min_value = k.pop("min", 0)
        max_value = k.pop("max", 100)
        return [
            model_ref(**factory.build(faker=faker, **k).model_dump(exclude=model_ref_exclude))
            for i in range(faker.random_int(min=min_value, max=max_value))
        ]

    field.callback = callback

    return field.callback(field, faker, parameters)


def BinaryField_callback(field: FactoryField, faker: Faker, parameters: dict[str, Any]) -> Any:
    edgy_field = field.owner.meta.model.meta.fields[field.name]
    min_value = parameters.pop("min", None)
    if min_value is not None:
        min_value = getattr(edgy_field, "min_length", min_value)
    if min_value is None:
        min_value = 0
    max_value = parameters.pop("max", None)
    if max_value is not None:
        max_value = getattr(edgy_field, "max_length", max_value)
    if max_value is None:
        max_value = 1024
    parameters.setdefault("length", faker.random_int(min=min_value, max=max_value))
    length = parameters.pop("length")
    return faker.binary(length)


def FileField_callback(field: FactoryField, faker: Faker, parameters: dict[str, Any]) -> Any:
    edgy_field = field.owner.meta.model.meta.fields[field.name]
    min_value = parameters.pop("min", None)
    if min_value is not None:
        min_value = getattr(edgy_field, "min_length", min_value)
    if min_value is None:
        min_value = 0
    max_value = parameters.pop("max", None)
    if max_value is not None:
        max_value = getattr(edgy_field, "max_length", max_value)
    if max_value is None:
        max_value = 1024
    parameters.setdefault("length", faker.random_int(min=min_value, max=max_value))
    length = parameters.pop("length")
    return File(faker.binary(length), name=faker.file_name(**parameters))


def ImageField_callback(field: FactoryField, faker: Faker, parameters: dict[str, Any]) -> Any:
    parameters.setdefault(
        "size",
        (
            faker.random_int(min=1, max=1024),
            faker.random_int(min=1, max=1024),
        ),
    )
    return faker.image(**parameters)


DEFAULT_MAPPING: dict[str, FactoryCallback | None] = {
    "IntegerField": edgy_field_param_extractor(
        "random_int",
        remapping={
            "gt": ("min", lambda edgy_field, attr_name, faker: getattr(edgy_field, attr_name) - 1),
            "lt": ("max", lambda edgy_field, attr_name, faker: getattr(edgy_field, attr_name) + 1),
        },
    ),
    "BigIntegerField": edgy_field_param_extractor(
        "random_int",
        remapping={
            "gt": ("min", lambda edgy_field, attr_name, faker: getattr(edgy_field, attr_name) - 1),
            "lt": ("max", lambda edgy_field, attr_name, faker: getattr(edgy_field, attr_name) + 1),
        },
    ),
    "SmallIntegerField": edgy_field_param_extractor(
        "random_int",
        remapping={
            "gt": ("min", lambda edgy_field, attr_name, faker: getattr(edgy_field, attr_name) - 1),
            "lt": ("max", lambda edgy_field, attr_name, faker: getattr(edgy_field, attr_name) + 1),
        },
    ),
    "DecimalField": edgy_field_param_extractor(
        "pydecimal",
        remapping={
            # TODO: find better definition
            "gt": (
                "min",
                lambda edgy_field, attr_name, faker: getattr(edgy_field, attr_name) - 0.0000000001,
            ),
            "lt": (
                "max",
                lambda edgy_field, attr_name, faker: getattr(edgy_field, attr_name) + 0.0000000001,
            ),
        },
    ),
    "FloatField": edgy_field_param_extractor(
        "pyfloat",
        remapping={
            # TODO: find better definition
            "gt": (
                "min",
                lambda edgy_field, attr_name, faker: getattr(edgy_field, attr_name) - 0.0000000001,
            ),
            "lt": (
                "max",
                lambda edgy_field, attr_name, faker: getattr(edgy_field, attr_name) + 0.0000000001,
            ),
        },
    ),
    "BooleanField": edgy_field_param_extractor("boolean"),
    "URLField": edgy_field_param_extractor("uri"),
    "ImageField": ImageField_callback,
    "FileField": FileField_callback,
    "ChoiceField": ChoiceField_callback,
    "CharField": edgy_field_param_extractor("name"),
    "DateField": edgy_field_param_extractor("date"),
    "DateTimeField": edgy_field_param_extractor("date_time"),
    "DurationField": edgy_field_param_extractor("time_delta"),
    "EmailField": edgy_field_param_extractor("email"),
    "BinaryField": BinaryField_callback,
    "IPAddressField": edgy_field_param_extractor("ipv4"),
    "PasswordField": edgy_field_param_extractor("password"),
    "TextField": edgy_field_param_extractor(
        "text",
        remapping={
            "max_length": (
                "max_nb_chars",
                lambda edgy_field, attr_name, faker: getattr(edgy_field, attr_name),
            ),
        },
    ),
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
    # Is only a backreference. Certainly not wanted except explicit specified.
    "RelatedField": None,
    # can't hold a value
    "ExcludeField": None,
    # private. Used by other fields to save a private value.
    "PlaceholderField": None,
}
