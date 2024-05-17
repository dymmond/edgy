import copy
from typing import TYPE_CHECKING, Any, Dict, Set, Tuple, Type

from pydantic._internal._model_construction import ModelMetaclass

from edgy.core.marshalls.config import ConfigMarshall
from edgy.core.marshalls.fields import BaseMarshallField
from edgy.core.utils.functional import extract_field_annotations_and_defaults
from edgy.exceptions import MarshallFieldDefinitionError

if TYPE_CHECKING:
    from edgy import Model
    from edgy.core.marshalls import Marshall


def handle_annotations(
    bases: Tuple[Type, ...], base_annotations: Dict[str, Any], attrs: Any
) -> Dict[str, Any]:
    """
    Handles and copies some of the annotations for
    initialiasation.
    """
    for base in bases:
        if hasattr(base, "__init_annotations__") and base.__init_annotations__:
            base_annotations.update(base.__init_annotations__)
        elif hasattr(base, "__annotations__") and base.__annotations__:
            base_annotations.update(base.__annotations__)

    annotations: Dict[str, Any] = {}
    if "__init_annotations__" in attrs:
        annotations = copy.copy(attrs["__init_annotations__"])
    else:
        if "__annotations__" in attrs:
            annotations = copy.copy(attrs["__annotations__"])

    annotations.update(base_annotations)
    return annotations


class MarshallMeta(ModelMetaclass):
    """
    Base metaclass for the Marshalls
    """

    __slots__ = ()

    def __new__(cls, name: str, bases: Tuple[Type, ...], attrs: Dict[str, Any]) -> Any:

        base_annotations: Dict[str, Any] = {}
        show_pk: bool = False
        marshall_config: ConfigMarshall = attrs.pop("marshall_config", None)
        attrs, model_fields = extract_field_annotations_and_defaults(attrs, BaseMarshallField)

        model_class = super().__new__

        parents = [parent for parent in bases if isinstance(parent, MarshallMeta)]
        if not parents:
            return model_class(cls, name, bases, attrs)

        model_class: "Marshall" = model_class(cls, name, bases, attrs)  # type: ignore
        if name in ("Marshall",):
            return model_class

        if marshall_config is None:
            raise MarshallFieldDefinitionError(
                "The 'marshall_config' was not found. Make sure it is declared and set."
            )

        # The declared model
        model: "Model" = marshall_config.get("model", None)  # type: ignore
        assert model is not None, "'model' must be declared in the 'ConfigMarshall'."

        base_fields_include = marshall_config.get("fields", None)
        base_fields_exclude = marshall_config.get("exclude", None)

        assert (
            base_fields_include is None or base_fields_exclude is None
        ), "Use either 'fields' or 'exclude', not both."
        assert (
            base_fields_include is not None or base_fields_exclude is not None
        ), "Either 'fields' or 'exclude' must be declared."

        base_model_fields: Dict[str, Any] = {}

        # Define the fields for the Marshall
        if base_fields_exclude is not None:
            base_model_fields = {
                k: v for k, v in model.model_fields.items() if k in base_fields_exclude
            }
        if "__all__" in base_fields_include:  # type: ignore
            base_model_fields = model.meta.fields_mapping
            show_pk = True
        else:
            base_model_fields = {
                k: v for k, v in model.model_fields.items() if k in base_fields_include  # type: ignore
            }

        base_model_fields.update(model_fields)

        # Handles with the fields not declared in the model.
        custom_fields: Dict[str, BaseMarshallField] = {}

        # For custom model_fields
        for k, v in attrs.items():
            if isinstance(v, BaseMarshallField):
                # Make sure the custom fields are flagged.
                if k not in model.model_fields:
                    custom_fields[k] = v

        # Handle the check of the custom fields
        for name, field in custom_fields.items():
            if field.__is_method__ and not field.source:
                if not hasattr(model_class, f"get_{name}"):
                    raise MarshallFieldDefinitionError(
                        f"Field '{name}' declared but no 'get_{name}' found in '{model_class.__name__}'."
                    )

        model_class.model_fields = base_model_fields

        # Handle annotations
        annotations: Dict[str, Any] = handle_annotations(bases, base_annotations, attrs)
        model_class.__init_annotations__ = annotations
        model_class.__show_pk__ = show_pk
        model_class.marshall_config = marshall_config
        model_class.model_fields.update(base_model_fields)
        model_class.model_rebuild(force=True)

        # Raise for error if any of the required fields is not in the Marshall
        required_fields: Set[str] = {k for k, v in model.model_fields.items() if not v.null}
        if any(value not in model_class.model_fields.keys() for value in required_fields):
            fields = ", ".join(required_fields)
            raise MarshallFieldDefinitionError(
                f"'{fields}' is required for the model '{model.__name__}'."
            )
        return model_class
