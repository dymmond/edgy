from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from monkay import load
from pydantic._internal._model_construction import ModelMetaclass

from edgy.core.db import models
from edgy.core.db.models.metaclasses import handle_annotations
from edgy.core.marshalls.config import ConfigMarshall
from edgy.core.marshalls.fields import BaseMarshallField
from edgy.core.utils.functional import extract_field_annotations_and_defaults
from edgy.exceptions import MarshallFieldDefinitionError

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.marshalls.base import Marshall


def _make_pk_field_readonly(field: BaseFieldType) -> BaseFieldType:
    if not getattr(field, "primary_key", False):
        return field
    field = copy.copy(field)
    field.read_only = True
    return field


class MarshallMeta(ModelMetaclass):
    """
    Base metaclass for the Marshalls
    """

    __slots__ = ()

    def __new__(cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]) -> Any:
        base_annotations: dict[str, Any] = {}
        show_pk: bool = False
        marshall_config: ConfigMarshall = attrs.pop("marshall_config", None)
        # TODO: should have correct types
        attrs, model_fields = extract_field_annotations_and_defaults(attrs, BaseMarshallField)

        has_parents = any(isinstance(parent, MarshallMeta) for parent in bases)

        if not has_parents:
            return super().__new__(cls, name, bases, attrs)

        marshall_class: type[Marshall] = super().__new__(cls, name, bases, attrs)
        if marshall_config is None:
            raise MarshallFieldDefinitionError(
                "The 'marshall_config' was not found. Make sure it is declared and set."
            )

        # The declared model
        _model: type[models.Model] | str | None = marshall_config.get("model", None)
        assert _model is not None, "'model' must be declared in the 'ConfigMarshall'."

        if isinstance(_model, str):
            model: type[models.Model] = load(_model)
            marshall_config["model"] = model
        else:
            model = _model

        base_fields_include = marshall_config.get("fields", None)
        base_fields_exclude = marshall_config.get("exclude", None)

        assert base_fields_include is None or base_fields_exclude is None, (
            "Use either 'fields' or 'exclude', not both."
        )
        assert base_fields_include is not None or base_fields_exclude is not None, (
            "Either 'fields' or 'exclude' must be declared."
        )

        base_marshall_model_fields: dict[str, Any]

        # Define the fields for the Marshall
        if base_fields_exclude is not None:
            base_marshall_model_fields = {
                k: v
                for k, v in model.model_fields.items()
                if k not in base_fields_exclude and not getattr(v, "exclude", False)
            }
        elif base_fields_include is not None and "__all__" in base_fields_include:
            base_marshall_model_fields = {
                k: v
                for k, v in model.model_fields.items()
                if k not in model_fields and not getattr(v, "exclude", False)
            }
            show_pk = True
        else:
            base_marshall_model_fields = {
                k: v for k, v in model.model_fields.items() if k in base_fields_include
            }
        if marshall_config.get("exclude_autoincrement", False):
            base_marshall_model_fields = {
                k: v
                for k, v in base_marshall_model_fields.items()
                if not getattr(v, "autoincrement", False)
            }
        if marshall_config.get("primary_key_read_only", False):
            base_marshall_model_fields = {
                k: _make_pk_field_readonly(v) for k, v in base_marshall_model_fields.items()
            }

        if marshall_config.get("exclude_read_only", False):
            base_marshall_model_fields = {
                k: v
                for k, v in base_marshall_model_fields.items()
                if not getattr(v, "read_only", False)
            }
        base_marshall_model_fields.update(model_fields)

        # Handles with the fields not declared in the model.
        custom_fields: dict[str, BaseMarshallField] = {}

        # For custom model_fields
        for k, v in attrs.items():
            if isinstance(v, BaseMarshallField):  # noqa: SIM102
                # Make sure the custom fields are flagged.
                if k not in model.meta.fields:
                    custom_fields[k] = v

        # Handle the check of the custom fields
        for name, field in custom_fields.items():
            if (
                field.__is_method__
                and not field.source
                and not hasattr(marshall_class, f"get_{name}")
            ):
                raise MarshallFieldDefinitionError(
                    f"Field '{name}' declared but no 'get_{name}' found in '{marshall_class.__name__}'."
                )

        model_fields_on_class = getattr(marshall_class, "__pydantic_fields__", None)
        if model_fields_on_class is None:
            model_fields_on_class = marshall_class.model_fields
        if "marshall_config" in model_fields_on_class:
            raise MarshallFieldDefinitionError(
                f"'marshall_config' is part of the fields of '{marshall_class.__name__}'. "
                "Did you forgot to annotate with 'ClassVar'?"
            )
        assert model_fields_on_class is not model.model_fields
        for key in model_fields:
            del model_fields_on_class[key]
        model_fields_on_class.update(base_marshall_model_fields)

        # Handle annotations
        annotations: dict[str, Any] = handle_annotations(bases, base_annotations, attrs)
        marshall_class.__init_annotations__ = annotations
        marshall_class.__show_pk__ = show_pk
        marshall_class.__custom_fields__ = custom_fields
        marshall_class.marshall_config = marshall_config

        # Fields which are required for a setup
        required_fields: set[str] = {k for k, v in model.model_fields.items() if v.is_required()}
        marshall_class.__incomplete_fields__ = tuple(
            sorted(name for name in required_fields if name not in model_fields_on_class)
        )
        if marshall_class.__incomplete_fields__:
            marshall_class.__lazy__ = True
        marshall_class.model_rebuild(force=True)
        return marshall_class
