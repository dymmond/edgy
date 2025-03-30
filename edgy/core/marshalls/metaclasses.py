import contextlib
from typing import TYPE_CHECKING, Any, Union, cast

from monkay import load
from pydantic._internal._model_construction import ModelMetaclass

from edgy.core.db.models.metaclasses import handle_annotations
from edgy.core.marshalls.config import ConfigMarshall
from edgy.core.marshalls.fields import BaseMarshallField
from edgy.core.utils.functional import extract_field_annotations_and_defaults
from edgy.exceptions import MarshallFieldDefinitionError

if TYPE_CHECKING:
    from edgy.core.db.models import Model
    from edgy.core.marshalls import Marshall


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

        model_class: type[Marshall] = super().__new__(cls, name, bases, attrs)
        if name in ("Marshall",):
            return model_class

        if marshall_config is None:
            raise MarshallFieldDefinitionError(
                "The 'marshall_config' was not found. Make sure it is declared and set."
            )

        # The declared model
        _model: Union[type[Model], str, None] = marshall_config.get("model", None)
        assert _model is not None, "'model' must be declared in the 'ConfigMarshall'."

        if isinstance(_model, str):
            model: type[Model] = load(_model)
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

        base_model_fields: dict[str, Any] = {}

        # Define the fields for the Marshall
        if base_fields_exclude is not None:
            base_model_fields = {
                k: v for k, v in model.model_fields.items() if k not in base_fields_exclude
            }
        elif base_fields_include is not None and "__all__" in base_fields_include:
            base_model_fields = {
                k: v for k, v in model.meta.fields.items() if k not in model_fields
            }
            show_pk = True
        else:
            base_model_fields = {
                k: v for k, v in model.model_fields.items() if k in base_fields_include
            }

        base_model_fields.update(model_fields)

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
                and not hasattr(model_class, f"get_{name}")
            ):
                raise MarshallFieldDefinitionError(
                    f"Field '{name}' declared but no 'get_{name}' found in '{model_class.__name__}'."
                )

        # required since pydantic 2.10
        model_class.__pydantic_fields__ = model_fields
        # error since pydantic 2.10
        with contextlib.suppress(AttributeError):
            model_class.model_fields = model_fields  # type: ignore

        # Handle annotations
        annotations: dict[str, Any] = handle_annotations(bases, base_annotations, attrs)
        model_class.__init_annotations__ = annotations
        model_class.__show_pk__ = show_pk
        model_class.__custom_fields__ = custom_fields
        model_class.marshall_config = marshall_config
        model_class.model_fields.update(base_model_fields)
        model_class.model_rebuild(force=True)

        # Raise for error if any of the required fields is not in the Marshall
        required_fields: set[str] = {
            f"{k}" for k, v in model.model_fields.items() if v.is_required()
        }
        model_fields = model_class.model_fields
        if any(value not in cast(dict, model_fields) for value in required_fields):
            fields = ", ".join(f"'{x}'" for x in sorted(required_fields))
            raise MarshallFieldDefinitionError(
                f"'{model.__name__}' model requires the following mandatory fields: [{fields}]."
            )
        return model_class
