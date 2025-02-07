from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from edgy.core.db.relationships.related_field import RelatedField
from edgy.core.files import File

from .utils import edgy_field_param_extractor, remove_unparametrized_relationship_fields

if TYPE_CHECKING:
    import enum

    from .fields import FactoryField
    from .types import FactoryCallback, ModelFactoryContext


def ChoiceField_callback(
    field: FactoryField, context: ModelFactoryContext, parameters: dict[str, Any]
) -> Any:
    choices: type[enum.Enum] = field.owner.meta.model.meta.fields[field.name].choices

    return context["faker"].enum(choices)


def ForeignKey_callback(
    field: FactoryField, context: ModelFactoryContext, parameters: dict[str, Any]
) -> Any:
    from .base import ModelFactory

    edgy_field = field.owner.meta.model.meta.fields[field.name]
    target = edgy_field.target

    class ForeignKeyFactory(ModelFactory, model_validation="none"):
        class Meta:
            model = target

    factory = ForeignKeyFactory()

    # arm callback
    def callback(field: FactoryField, context: ModelFactoryContext, k: dict[str, Any]) -> Any:
        remove_unparametrized_relationship_fields(target, k, {edgy_field.related_name})
        return factory.build(**k)

    field.callback = callback
    return field.callback(field, context, parameters)


def ManyToManyField_callback(
    field: FactoryField, context: ModelFactoryContext, parameters: dict[str, Any]
) -> Any:
    from .base import ModelFactory

    edgy_field = field.owner.meta.model.meta.fields[field.name]
    target = edgy_field.target

    class ManyToManyFieldFactory(ModelFactory, model_validation="none"):
        class Meta:
            model = target

    factory = ManyToManyFieldFactory()

    # arm callback
    def callback(field: FactoryField, context: ModelFactoryContext, k: dict[str, Any]) -> Any:
        remove_unparametrized_relationship_fields(target, k, {edgy_field.related_name})
        min_value = k.pop("min", 0)
        max_value = k.pop("max", 10)
        return [
            factory.build(**k)
            for i in range(context["faker"].random_int(min=min_value, max=max_value))
        ]

    field.callback = callback

    return field.callback(field, context, parameters)


def RefForeignKey_callback(
    field: FactoryField, context: ModelFactoryContext, parameters: dict[str, Any]
) -> Any:
    from .base import ModelFactory

    edgy_model = field.owner.meta.model
    edgy_model_meta = edgy_model.meta
    model_ref = edgy_model_meta.fields[field.name].to
    edgy_field = edgy_model_meta.fields[model_ref.__related_name__]

    if isinstance(edgy_field, RelatedField):
        factory_model = edgy_field.related_from
        field_excluded: str | Literal[False] = edgy_field.foreign_key_name
    else:
        factory_model = edgy_field.target
        field_excluded = edgy_field.related_name

    class RefForeignKeyFactory(ModelFactory, model_validation="none"):
        class Meta:
            model = factory_model

    factory = RefForeignKeyFactory()
    model_ref_exclude: set[str] = set()
    model_fields = model_ref.model_fields
    for field_name in edgy_model_meta.fields:
        if field_name not in model_fields:
            model_ref_exclude.add(field_name)

    def callback(field: FactoryField, context: ModelFactoryContext, k: dict[str, Any]) -> Any:
        remove_unparametrized_relationship_fields(factory_model, k, {field_excluded})
        min_value = k.pop("min", 0)
        max_value = k.pop("max", 10)
        return [
            model_ref(**factory.build_values(**k))
            for i in range(context["faker"].random_int(min=min_value, max=max_value))
        ]

    field.callback = callback

    return field.callback(field, context, parameters)


def BinaryField_callback(
    field: FactoryField, context: ModelFactoryContext, parameters: dict[str, Any]
) -> Any:
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
    parameters.setdefault("length", context["faker"].random_int(min=min_value, max=max_value))
    length = parameters.pop("length")
    return context["faker"].binary(length)


def FileField_callback(
    field: FactoryField, context: ModelFactoryContext, parameters: dict[str, Any]
) -> Any:
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
    parameters.setdefault("length", context["faker"].random_int(min=min_value, max=max_value))
    length = parameters.pop("length")
    return File(context["faker"].binary(length), name=context["faker"].file_name(**parameters))


def ImageField_callback(
    field: FactoryField, context: ModelFactoryContext, parameters: dict[str, Any]
) -> Any:
    parameters.setdefault(
        "size",
        (
            context["faker"].random_int(min=1, max=1024),
            context["faker"].random_int(min=1, max=1024),
        ),
    )
    return context["faker"].image(**parameters)


DEFAULT_MAPPING: dict[str, FactoryCallback | None] = {
    "IntegerField": edgy_field_param_extractor(
        "random_int",
        remapping={
            "gt": (
                "min",
                lambda edgy_field, attr_name, context: getattr(edgy_field, attr_name) - 1,
            ),
            "lt": (
                "max",
                lambda edgy_field, attr_name, context: getattr(edgy_field, attr_name) + 1,
            ),
        },
    ),
    "BigIntegerField": edgy_field_param_extractor(
        "random_int",
        remapping={
            "gt": (
                "min",
                lambda edgy_field, attr_name, context: getattr(edgy_field, attr_name) - 1,
            ),
            "lt": (
                "max",
                lambda edgy_field, attr_name, context: getattr(edgy_field, attr_name) + 1,
            ),
        },
    ),
    "SmallIntegerField": edgy_field_param_extractor(
        "random_int",
        remapping={
            "gt": (
                "min",
                lambda edgy_field, attr_name, context: getattr(edgy_field, attr_name) - 1,
            ),
            "lt": (
                "max",
                lambda edgy_field, attr_name, context: getattr(edgy_field, attr_name) + 1,
            ),
        },
    ),
    "DecimalField": edgy_field_param_extractor(
        "pydecimal",
        remapping={
            # TODO: find better definition
            "gt": (
                "min",
                lambda edgy_field, attr_name, context: getattr(edgy_field, attr_name)
                - 0.0000000001,
            ),
            "lt": (
                "max",
                lambda edgy_field, attr_name, context: getattr(edgy_field, attr_name)
                + 0.0000000001,
            ),
        },
    ),
    "FloatField": edgy_field_param_extractor(
        "pyfloat",
        remapping={
            # TODO: find better definition
            "gt": (
                "min",
                lambda edgy_field, attr_name, context: getattr(edgy_field, attr_name)
                - 0.0000000001,
            ),
            "lt": (
                "max",
                lambda edgy_field, attr_name, context: getattr(edgy_field, attr_name)
                + 0.0000000001,
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
                lambda edgy_field, attr_name, context: getattr(edgy_field, attr_name),
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
    "PGArrayField": None,
    "CompositeField": None,
    "ComputedField": None,
    "PKField": None,
    # Is only a backreference. Certainly not wanted except explicit specified. Leads to loopbacks when autobuild
    "RelatedField": None,
    # can't hold a value
    "ExcludeField": None,
    # private. Used by other fields to save a private value.
    "PlaceholderField": None,
}
