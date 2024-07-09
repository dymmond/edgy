import typing
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Type

from orjson import OPT_OMIT_MICROSECONDS, OPT_SERIALIZE_NUMPY, dumps
from pydantic import ConfigDict

import edgy
from edgy.core.db.fields.base import BaseField

if TYPE_CHECKING:
    from edgy import Model
    from edgy.core.db.models.metaclasses import MetaInfo

type_ignored_setattr = setattr


class DateParser:

    def _resolve_value(self, value: typing.Any) -> typing.Any:
        if isinstance(value, dict):
            return dumps(
                value,
                option=OPT_SERIALIZE_NUMPY | OPT_OMIT_MICROSECONDS,
            ).decode("utf-8")
        elif isinstance(value, Enum):
            return value.name
        return value


class ModelParser:
    def _extract_model_references(self, extracted_values: Any, model_class: Optional[Type["Model"]]) -> Any:
        """
        Exracts any possible model references from the EdgyModel and returns a dictionary.
        """
        model_references = {
            name: extracted_values.get(name, None)
            for name in model_class.meta.model_references.keys()  # type: ignore
            if extracted_values.get(name)
        }
        return model_references

    def _extract_values_from_field(
        self,
        extracted_values: Any,
        model_class: Optional["Model"] = None,
        is_update: bool = False,
        is_partial: bool = False,
    ) -> Any:
        """
        Extracts all the default values from the given fields and returns the raw
        value corresponding to each field.
        """
        model_cls = model_class or self
        validated: Dict[str, Any] = {}
        # phase 1: transform when required
        if model_cls.meta.input_modifying_fields:
            extracted_values = {**extracted_values}
            for field_name in model_cls.meta.input_modifying_fields:
                model_cls.fields[field_name].modify_input(field_name, extracted_values)
        # phase 2: validate fields and set defaults for readonly
        need_second_pass: List[BaseField] = []
        for field_name, field in model_cls.meta.fields_mapping.items():
            if (not is_partial or (field.inject_default_on_partial_update and is_update)) and field.read_only:
                if field.has_default():
                    validated.update(field.get_default_values(field_name, validated, is_update=is_update))
                continue
            if field_name in extracted_values:
                item = extracted_values[field_name]
                for sub_name, value in field.clean(field_name, item).items():
                    if sub_name in validated:
                        raise ValueError(f"value set twice for key: {sub_name}")
                    validated[sub_name] = value
            elif (not is_partial or (field.inject_default_on_partial_update and is_update)) and field.has_default():
                # add field without a value to the second pass (in case no value appears)
                # only include fields which have inject_default_on_partial_update set or if not is_partial
                need_second_pass.append(field)

        # phase 3: set defaults for the rest if not partial or inject_default_on_partial_update
        if need_second_pass:
            for field in need_second_pass:
                # check if field appeared e.g. by composite
                if field.name not in validated:
                    validated.update(field.get_default_values(field.name, validated, is_update=is_update))
        # Update with any ModelRef
        validated.update(self._extract_model_references(extracted_values, model_cls))
        return validated


def create_edgy_model(
    __name__: str,
    __module__: str,
    __definitions__: Optional[Dict[Any, Any]] = None,
    __metadata__: Optional[Type["MetaInfo"]] = None,
    __qualname__: Optional[str] = None,
    __config__: Optional[ConfigDict] = None,
    __bases__: Optional[Tuple[Type["Model"]]] = None,
    __proxy__: bool = False,
    __pydantic_extra__: Any = None,
) -> Type["Model"]:
    """
    Generates an `edgy.Model` with all the required definitions to generate the pydantic
    like model.
    """

    if not __bases__:
        __bases__ = (edgy.Model,)

    qualname = __qualname__ or __name__
    core_definitions = {
        "__module__": __module__,
        "__qualname__": qualname,
        "is_proxy_model": __proxy__,
    }
    if not __definitions__:
        __definitions__ = {}

    core_definitions.update(**__definitions__)

    if __config__:
        core_definitions.update(**{"model_config": __config__})
    if __metadata__:
        core_definitions.update(**{"Meta": __metadata__})
    if __pydantic_extra__:
        core_definitions.update(**{"__pydantic_extra__": __pydantic_extra__})

    model: Type["Model"] = type(__name__, __bases__, core_definitions)
    return model


def generify_model_fields(model: Type["Model"]) -> Dict[Any, Any]:
    """
    Makes all fields generic when a partial model is generated or used.
    This also removes any metadata for the field such as validations making
    it a clean slate to be used internally to process dynamic data and removing
    the constraints of the original model fields.
    """
    fields = {}

    # handle the nested non existing results
    for name, field in model.model_fields.items():
        type_ignored_setattr(field, "annotation", Any)
        type_ignored_setattr(field, "null", True)
        type_ignored_setattr(field, "metadata", [])
        fields[name] = field
    return fields
