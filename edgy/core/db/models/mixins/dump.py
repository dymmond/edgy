from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

import orjson
from pydantic import BaseModel

from edgy.core.db.context_vars import (
    MODEL_GETATTR_BEHAVIOR,
)

if TYPE_CHECKING:
    from edgy.core.db.models.metaclasses import MetaInfo

_empty = cast(set[str], frozenset())


class DumpMixin:
    """
    A mixin class providing enhanced model dumping functionalities for Pydantic models.

    This mixin extends the default `model_dump` behavior of Pydantic models
    to handle complex scenarios such as primary key visibility, excluded fields,
    and fields with custom getter methods or special serialization requirements,
    especially for relationships and composite fields.
    """

    meta: ClassVar[MetaInfo]
    """
    A class variable holding metadata about the model, including field definitions,
    special getter fields, and foreign key relationships. This metadata is crucial
    for determining how fields should be processed during the dumping operation.
    """

    def model_dump(self: BaseModel, show_pk: bool | None = None, **kwargs: Any) -> dict[str, Any]:
        """
        An updated and enhanced version of the Pydantic `model_dump` method.

        This method provides fine-grained control over how the model's data is
        serialized into a dictionary. It specifically addresses:
        -   Enforcing the inclusion of primary key fields.
        -   Correctly handling fields marked for exclusion.
        -   Applying custom logic for fields that retrieve their values via getters
            or require special serialization (e.g., related models, composite fields).

        Args:
            self: The instance of the Pydantic `BaseModel` on which `model_dump` is called.
            show_pk: An optional boolean flag. If `True`, the primary key field(s) will
                     always be included in the dumped dictionary, even if they are
                     otherwise excluded or not explicitly included. If `None`, the
                     default behavior defined by `self.__show_pk__` will be used.
            **kwargs: Arbitrary keyword arguments that are passed directly to the
                      underlying Pydantic `super().model_dump` method. These can
                      include `exclude`, `include`, `mode`, etc.

        Returns:
            A `dict` representing the serialized model data, with applied
            inclusions, exclusions, and special field handling.
        """
        meta = self.meta
        # Retrieve the 'exclude' argument, defaulting to None if not provided.
        # This argument can be a set of field names, a dictionary mapping field
        # names to boolean exclusion flags, or None.
        _exclude: set[str] | dict[str, Any] | None = kwargs.pop("exclude", None)

        # Initialize variables for managing field exclusions.
        # `initial_full_field_exclude` will contain names of fields to be fully excluded.
        # `exclude_passed` is a dictionary used for the first pass of `super().model_dump`.
        # `exclude_second_pass` is used for fields processed in the second pass (e.g., getters).
        if _exclude is None:
            initial_full_field_exclude: set[str] = _empty
            # Must be a writable dictionary to allow modifications.
            exclude_passed: dict[str, Any] = {}
            exclude_second_pass: dict[str, Any] = {}
        elif isinstance(_exclude, dict):
            # If `_exclude` is a dictionary, extract fields marked for full exclusion (value is True).
            initial_full_field_exclude = {k for k, v in _exclude.items() if v is True}
            # Create a copy for `exclude_passed` to avoid modifying the original `_exclude`.
            exclude_passed = copy.copy(_exclude)
            exclude_second_pass = _exclude
        else:
            # If `_exclude` is a set or list, convert it to a set for consistency.
            initial_full_field_exclude = set(_exclude)
            # Create dictionaries where all initially excluded fields are marked `True`.
            exclude_passed = dict.fromkeys(initial_full_field_exclude, True)
            exclude_second_pass = exclude_passed.copy()

        # `need_second_pass` will store field names that require a second processing pass.
        # These are typically fields with custom getters or foreign keys to models
        # that need special serialization.
        need_second_pass: set[str] = set()

        # Process fields that have special getter methods defined.
        for field_name in meta.special_getter_fields:
            # Temporarily exclude these fields from the initial `model_dump` pass.
            exclude_passed[field_name] = True
            # If a special getter field was not explicitly excluded and is not marked
            # for exclusion in its `MetaInfo`, add it to `need_second_pass`.
            if (
                field_name not in initial_full_field_exclude
                and not meta.fields[field_name].exclude
            ):
                need_second_pass.add(field_name)

        # Process foreign key fields.
        for field_name in meta.foreign_key_fields:
            field = meta.fields[field_name]
            # If the foreign key field is already fully excluded, skip further processing.
            if field_name in initial_full_field_exclude or field.exclude:
                continue
            # If the target model of the foreign key needs special serialization,
            # temporarily exclude it from the first pass and add to `need_second_pass`.
            if field.target.meta.needs_special_serialization:
                exclude_passed[field_name] = True
                need_second_pass.add(field_name)

        # Retrieve the 'include' argument, defaulting to None.
        include: set[str] | dict[str, Any] | None = kwargs.pop("include", None)
        # Determine the serialization mode ('json' or 'python').
        mode: Literal["json", "python"] = kwargs.pop("mode", "python")

        # Determine if the primary key should be shown, preferring the `show_pk`
        # argument over the model's internal `__show_pk__` attribute.
        should_show_pk = self.__show_pk__ if show_pk is None else show_pk

        # Perform the initial `model_dump` using Pydantic's default implementation.
        # This will handle most fields and apply the initial exclusion rules.
        result_dict: dict[str, Any] = super().model_dump(
            exclude=exclude_passed, include=include, mode=mode, **kwargs
        )

        # Set a context variable to control the behavior of `getattr` during the
        # second pass, often used to prevent recursive database queries.
        token = MODEL_GETATTR_BEHAVIOR.set("passdown")
        try:
            # Process fields identified in `need_second_pass`.
            for field_name in need_second_pass:
                # Skip the field if it's not a primary key (and `show_pk` is true)
                # or if it's not explicitly included (and `include` is not None).
                if not (
                    (should_show_pk and field_name in self.pknames)
                    or include is None
                    or field_name in include
                ):
                    continue

                field = meta.fields[field_name]
                try:
                    # Attempt to get the value of the field, which might trigger a getter.
                    retval = getattr(self, field_name)
                except AttributeError:
                    # If the attribute doesn't exist (e.g., not loaded), skip it.
                    continue

                sub_include = None
                # If `include` is a dictionary, extract specific inclusion rules for the sub-field.
                if isinstance(include, dict):
                    sub_include = include.get(field_name, None)
                    # If the sub-field is explicitly included with `True`, treat it as no specific
                    # sub-inclusion (i.e., include all sub-fields by default).
                    if sub_include is True:
                        sub_include = None

                # Get specific exclusion rules for the sub-field.
                sub_exclude = exclude_second_pass.get(field_name, None)
                # Ensure that a field marked for full exclusion in the first pass is not
                # unexpectedly processed in the second pass.
                assert sub_exclude is not True, "field should have been excluded"

                # If the retrieved value is another `BaseModel` (e.g., a related object),
                # recursively call `model_dump` on it.
                if isinstance(retval, BaseModel):
                    retval = retval.model_dump(
                        include=sub_include, exclude=sub_exclude, mode=mode, **kwargs
                    )
                else:
                    # For non-BaseModel values, `sub_include` and `sub_exclude` should not be present
                    # as they are only applicable to nested Pydantic models.
                    assert sub_include is None, "sub include filters for no pydantic model"
                    assert sub_exclude is None, "sub exclude filters for no pydantic model"
                    # If the mode is 'json' and the field is not marked for unsafe JSON serialization,
                    # skip it. This prevents non-serializable types from breaking JSON output.
                    if mode == "json" and not getattr(field, "unsafe_json_serialization", False):
                        # skip field if it isn't a BaseModel and the mode is json and
                        # unsafe_json_serialization is not set
                        # Currently, `unsafe_json_serialization` exists only on `CompositeFields`.
                        continue

                # Determine the alias for the field in the dumped dictionary.
                # Prioritize `serialization_alias`, then `alias`, otherwise use the field name.
                alias: str = field_name
                if getattr(field, "serialization_alias", None):
                    alias = cast(str, field.serialization_alias)
                elif getattr(field, "alias", None):
                    alias = field.alias
                # Add the processed field and its value to the `result_dict`.
                result_dict[alias] = retval
        finally:
            # Reset the `MODEL_GETATTR_BEHAVIOR` context variable to its previous state.
            MODEL_GETATTR_BEHAVIOR.reset(token)
        return result_dict

    def model_dump_json(self, **kwargs: Any) -> str:
        """
        Dumps the model data into a JSON string.

        This method leverages `model_dump` with `mode="json"` and then uses `orjson`
        for efficient JSON serialization, which is faster than Python's built-in `json` module.

        Args:
            self: The instance of the `BaseModel` to be dumped.
            **kwargs: Arbitrary keyword arguments passed to `model_dump`. These can
                      control inclusions, exclusions, and other dumping behaviors.

        Returns:
            A `str` representing the JSON serialization of the model data.
        """
        return orjson.dumps(self.model_dump(mode="json", **kwargs)).decode()
