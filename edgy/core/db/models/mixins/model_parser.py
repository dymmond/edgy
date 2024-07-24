from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

if TYPE_CHECKING:
    from edgy import Model
    from edgy.core.db.fields.base import BaseFieldType


class ModelParser:
    def extract_model_references(
        self, extracted_values: Any, model_class: Optional[Type["BaseFieldType"]] = None
    ) -> Any:
        """
        Exracts any possible model references from the EdgyModel and returns a dictionary.
        """
        model_cls = model_class or self
        model_references = {
            name: extracted_values.get(name, None)
            for name in model_cls.meta.model_references  # type: ignore
            if extracted_values.get(name)
        }
        return model_references

    def extract_column_values(
        self,
        extracted_values: Any,
        model_class: Optional["Model"] = None,
        is_update: bool = False,
        is_partial: bool = False,
    ) -> Dict[str, Any]:
        """
        Extracts all the default values from the given fields and returns the raw
        value corresponding to each field.

        Extract the model references.
        """
        model_cls = model_class or self
        validated: Dict[str, Any] = {}
        # phase 1: transform when required
        if model_cls.meta.input_modifying_fields:
            extracted_values = {**extracted_values}
            for field_name in model_cls.meta.input_modifying_fields:
                model_cls.meta.fields[field_name].modify_input(field_name, extracted_values)
        # phase 2: validate fields and set defaults for readonly
        need_second_pass: List[BaseFieldType] = []
        for field_name, field in model_cls.meta.fields.items():
            if (
                not is_partial or (field.inject_default_on_partial_update and is_update)
            ) and field.read_only:
                if field.has_default():
                    validated.update(
                        field.get_default_values(field_name, validated, is_update=is_update)
                    )
                continue
            if field_name in extracted_values:
                item = extracted_values[field_name]
                for sub_name, value in field.clean(field_name, item).items():
                    if sub_name in validated:
                        raise ValueError(f"value set twice for key: {sub_name}")
                    validated[sub_name] = value
            elif (
                not is_partial or (field.inject_default_on_partial_update and is_update)
            ) and field.has_default():
                # add field without a value to the second pass (in case no value appears)
                # only include fields which have inject_default_on_partial_update set or if not is_partial
                need_second_pass.append(field)

        # phase 3: set defaults for the rest if not partial or inject_default_on_partial_update
        if need_second_pass:
            for field in need_second_pass:
                # check if field appeared e.g. by composite
                if field.name not in validated:
                    validated.update(
                        field.get_default_values(field.name, validated, is_update=is_update)
                    )
        return validated
