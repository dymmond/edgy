from __future__ import annotations

from inspect import getmro, isclass
from typing import TYPE_CHECKING, Any, Literal, cast

import monkay
from pydantic import ValidationError

from edgy.core.db.models import Model
from edgy.core.terminal import Print
from edgy.testing.exceptions import InvalidModelError
from edgy.utils.compat import is_class_and_subclass

from .fields import FactoryField
from .mappings import DEFAULT_MAPPING

if TYPE_CHECKING:
    from .base import ModelFactory
    from .types import FactoryCallback


terminal = Print()


# this is not models MetaInfo
class MetaInfo:
    __slots__ = ("model", "fields", "faker", "mappings", "callcounts")
    model: type[Model]
    mappings: dict[str, FactoryCallback | None]

    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        self.fields: dict[str, FactoryField] = {}
        self.mappings: dict[str, FactoryCallback | None] = {}
        self.callcounts: dict[int, int] = {}
        for slot in self.__slots__:
            value = getattr(meta, slot, None)
            if value is not None:
                setattr(self, slot, value)
        for name, value in kwargs.items():
            setattr(self, name, value)


class ModelFactoryMeta(type):
    def __new__(
        cls,
        factory_name: str,
        bases: tuple[type, ...],
        attrs: dict[str, Any],
        meta_info_class: type[MetaInfo] = MetaInfo,
        model_validation: Literal["none", "warn", "error", "pedantic"] = "warn",
        **kwargs: Any,
    ) -> type[ModelFactory]:
        # has parents
        if not any(True for parent in bases if isinstance(parent, ModelFactoryMeta)):
            return super().__new__(cls, factory_name, bases, attrs, **kwargs)  # type: ignore
        try:
            from faker import Faker
        except ImportError:
            raise ImportError('"Faker" is required for the ModelFactory.') from None
        faker = Faker()
        meta_class: Any = attrs.pop("Meta", None)
        fields: dict[str, FactoryField] = {}
        mappings: dict[str, FactoryCallback] = {}
        # of the current Meta
        current_mapping: dict[str, FactoryCallback | None] = (
            getattr(meta_class, "mappings", None) or {}
        )
        for name, mapping in current_mapping.items():
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
        meta_info = meta_info_class(model=db_model, faker=faker, mappings=mappings)

        defaults: dict[str, Any] = {}
        # update fields and collect defaults (values matching to parameters)
        for key in list(attrs.keys()):
            if key == "meta" or key == "exclude_autoincrement":
                continue
            value: Any = attrs.get(key)
            if isinstance(value, FactoryField):
                value.original_name = key
                del attrs[key]
                value.name = field_name = value.name or key
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
                    fields[field_name] = value
            elif key in db_model.meta.fields:
                defaults[key] = value

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

        new_class = cast(
            type["ModelFactory"], super().__new__(cls, factory_name, bases, attrs, **kwargs)
        )
        # add the defaults
        new_class.__defaults__ = defaults

        # set owner
        for field in fields.values():
            field.owner = new_class

        # validate
        if model_validation != "none":
            try:
                # we don't want to updat ethe counts yet
                new_class().build(callcounts={})
            except ValidationError as exc:
                if model_validation == "pedantic":
                    raise exc
            except Exception as exc:
                if model_validation == "error" or model_validation == "pedantic":
                    raise exc
                terminal.write_warning(
                    f'"{factory_name}" failed producing a valid sample model: "{exc!r}".'
                )
        return new_class
