from __future__ import annotations

import copy
import inspect
from collections.abc import Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    cast,
)

from pydantic import BaseModel

from edgy.core.db.constants import ConditionalRedirect
from edgy.core.db.context_vars import FALLBACK_TARGET_REGISTRY, MODEL_GETATTR_BEHAVIOR
from edgy.core.db.fields.base import BaseCompositeField
from edgy.core.db.fields.core import FieldFactory
from edgy.core.db.fields.types import BaseFieldType
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType


class ConcreteCompositeField(BaseCompositeField):
    """
    Represents a concrete implementation of a composite field, designed
    for internal use within Edgy.

    This field allows grouping multiple sub-fields together, which can be
    either explicitly defined or absorbed from an existing model's fields.
    It handles embedding, naming conventions, and asynchronous retrieval of
    its constituent parts.

    Attributes:
        prefix_embedded: A string prefix added to embedded field names.
        prefix_column_name: A string prefix added to embedded field column names.
        unsafe_json_serialization: If True, allows unsafe JSON serialization of
                                   the composite field's content.
        absorb_existing_fields: If True, the composite field will absorb and
                                override existing fields with the same name during
                                embedding.
        model: An optional Pydantic `BaseModel` or `ConditionalRedirect` type that
               this composite field represents or redirects to.
    """

    prefix_embedded: str = ""
    prefix_column_name: str = ""
    unsafe_json_serialization: bool = False
    absorb_existing_fields: bool = False
    model: type[BaseModel] | type[ConditionalRedirect] | None = None

    def __init__(
        self,
        *,
        inner_fields: (
            Sequence[str | tuple[str, BaseFieldType]] | type[BaseModelType] | dict[str, Any]
        ) = (),
        **kwargs: Any,
    ) -> None:
        """
        Initializes a new `ConcreteCompositeField` instance.

        This constructor processes the `inner_fields` argument, which can be
        a sequence of field names or field definitions, a model class, or a
        dictionary of fields. It prepares the internal lists and dictionaries
        for managing these sub-fields.

        Args:
            inner_fields: A collection of field definitions or a model type to
                          extract fields from.
            **kwargs: Additional keyword arguments to be passed to the `BaseField`
                      constructor, such as `owner`, `model`, and `inherit`.

        Raises:
            FieldDefinitionError: If a field name collision occurs with prefixes.
        """
        self.inner_field_names: list[str] = []
        self.embedded_field_defs: dict[str, BaseFieldType] = {}

        # If inner_fields is a model with a 'meta' attribute, extract its fields.
        if hasattr(inner_fields, "meta"):
            kwargs.setdefault("model", inner_fields)
            kwargs.setdefault("inherit", inner_fields.meta.inherit)
            inner_fields = inner_fields.meta.fields
        # If inner_fields is a dictionary, convert it to an items view.
        if isinstance(inner_fields, dict):
            inner_fields = inner_fields.items()  # type: ignore

        # Extract 'owner' and 'model' from kwargs.
        owner = kwargs.get("owner")
        self.model = kwargs.pop("model", self.model)

        # If a model is provided and it's a subclass of BaseModel,
        # set the field_type and annotation accordingly.
        if self.model is not None and issubclass(self.model, BaseModel):
            kwargs["field_type"] = self.model
            kwargs["annotation"] = self.model

        # Call the parent BaseCompositeField constructor.
        # This field acts as a holder, so it is nullable by default.
        super().__init__(null=True, **kwargs)

        # Process each inner field definition.
        for field in inner_fields:
            if isinstance(field, str):
                # If it's a string, simply add the name to inner_field_names.
                self.inner_field_names.append(field)
            elif field[1].inherit:
                # If the field should inherit (not excluded like PKField).
                field_name = field[0]
                # Check for after the transformation invalid field names when adding prefix.
                if self.prefix_embedded.endswith("_") and field_name.startswith("_"):
                    raise FieldDefinitionError(
                        f"_ prefixed fields are not supported: {field_name} with "
                        f"prefix ending with _"
                    )
                # Apply the embedded prefix to the field name.
                field_name = f"{self.prefix_embedded}{field_name}"
                # Embed the field, setting its new name and owner.
                field_def = field[1].embed_field(
                    self.prefix_embedded, field_name, owner=owner, parent=self
                )
                if field_def is not None:
                    # Exclude the embedded field from default Pydantic serialization.
                    field_def.exclude = True
                    self.inner_field_names.append(field_def.name)
                    self.embedded_field_defs[field_def.name] = field_def

    def translate_name(self, name: str) -> str:
        """
        Translates an embedded field's name by removing its prefix,
        if applicable.

        This method is used when converting internal field names back to
        their original, un-prefixed form for external representation (e.g.,
        in Pydantic models).

        Args:
            name: The internal name of the field, potentially with a prefix.

        Returns:
            The translated (un-prefixed) name of the field.
        """
        # If there's an embedded prefix and the name exists in embedded field definitions,
        # remove the prefix from the name.
        if self.prefix_embedded and name in self.embedded_field_defs:
            return name.removeprefix(self.prefix_embedded)
        # Otherwise, return the name as is.
        return name

    def embed_field(
        self,
        prefix: str,
        new_fieldname: str,
        owner: type[BaseModelType] | None = None,
        parent: BaseFieldType | None = None,
    ) -> BaseFieldType:
        """
        Embeds this composite field into another field, applying a new prefix
        and updating its internal sub-fields.

        This method is crucial for handling nested composite fields, ensuring
        that all sub-fields inherit the correct naming conventions and ownership.

        Args:
            prefix: The prefix to be applied to all sub-fields.
            new_fieldname: The new full name of this composite field itself.
            owner: The new owner model class for the embedded composite field.
            parent: The parent field if this field is being embedded within another
                    composite field.

        Returns:
            A copy of this composite field with updated prefixes and embedded
            sub-fields.

        Raises:
            FieldDefinitionError: If a field name collision occurs due to invalid prefixes.
        """
        # Create a copy of the field and apply the new fieldname and owner.
        field_copy = cast(
            BaseFieldType, super().embed_field(prefix, new_fieldname, owner=owner, parent=parent)
        )
        # Update the embedded prefix for the copied field.
        field_copy.prefix_embedded = f"{prefix}{field_copy.prefix_embedded}"
        # If the parent has a prefix_column_name, apply it to the copied field's
        # column name prefix.
        if getattr(parent, "prefix_column_name", None):
            field_copy.prefix_column_name = (
                f"{parent.prefix_column_name}{field_copy.prefix_embedded or ''}"  # type: ignore
            )
        # Store the current embedded_field_defs before modification.
        embedded_field_defs = field_copy.embedded_field_defs
        # Update inner_field_names with the new prefix, excluding already embedded fields.
        field_copy.inner_field_names = [
            f"{prefix}{field_name}"
            for field_name in field_copy.inner_field_names
            if field_name not in embedded_field_defs
        ]
        # Reset embedded_field_defs for the copy.
        field_copy.embedded_field_defs = {}
        # Iterate through previously embedded field definitions.
        for field_name, field in embedded_field_defs.items():
            # Check for invalid field names with prefix.
            if self.prefix_embedded.endswith("_") and field_name.startswith("_"):
                raise FieldDefinitionError(
                    f"_ prefixed fields are not supported: {field_name} with prefix ending with _"
                )
            # Apply the new prefix to the field name.
            field_name = f"{prefix}{field_name}"
            # Recursively embed the sub-field.
            field_def = field.embed_field(prefix, field_name, owner=owner, parent=field_copy)
            if field_def is not None:
                field_def.exclude = True
                field_copy.inner_field_names.append(field_def.name)
                field_copy.embedded_field_defs[field_def.name] = field_def
        return field_copy

    async def aget(self, instance: BaseModelType, owner: Any = None) -> dict[str, Any] | Any:
        """
        Asynchronously retrieves the values of the composite field's sub-fields.

        This method is used when the composite field needs to be loaded asynchronously,
        for example, when sub-fields might involve database fetches. It ensures
        that awaitable sub-field values are properly awaited.

        Args:
            instance: The model instance from which to retrieve sub-field values.
            owner: The owner class (not typically used for instance access).

        Returns:
            A dictionary containing the sub-field values, or a Pydantic model
            instance if `self.model` is set.
        """
        d = {}
        # Set the MODEL_GETATTR_BEHAVIOR to "coro" to indicate an asynchronous context.
        token = MODEL_GETATTR_BEHAVIOR.set("coro")
        try:
            for key in self.inner_field_names:
                translated_name = self.translate_name(key)
                value = getattr(instance, key)
                # If the value is awaitable, await it.
                if inspect.isawaitable(value):
                    value = await value
                d[translated_name] = value
        finally:
            # Reset MODEL_GETATTR_BEHAVIOR to its previous state.
            MODEL_GETATTR_BEHAVIOR.reset(token)

        # If a Pydantic model is associated and it's not a ConditionalRedirect.
        if self.model is not None and self.model is not ConditionalRedirect:
            # If a fallback registry is already set, create the model directly.
            if FALLBACK_TARGET_REGISTRY.get() is not None:
                return self.model(**d)
            # Temporarily set the fallback registry to the owner's registry.
            token2 = FALLBACK_TARGET_REGISTRY.set(self.owner.meta.registry or None)
            try:
                return self.model(**d)
            finally:
                # Reset the fallback registry.
                FALLBACK_TARGET_REGISTRY.reset(token2)
        return d

    def __get__(self, instance: BaseModelType, owner: Any = None) -> dict[str, Any] | Any:
        """
        Descriptor method to retrieve the values of the composite field's sub-fields.

        This method handles both synchronous and asynchronous retrieval (by delegating
        to `aget` if `MODEL_GETATTR_BEHAVIOR` is 'coro'). It constructs a dictionary
        of sub-field values or an instance of the associated Pydantic model.

        Args:
            instance: The model instance from which to retrieve sub-field values.
            owner: The owner class (not typically used for instance access).

        Returns:
            A dictionary containing the sub-field values, or a Pydantic model
            instance if `self.model` is set.

        Raises:
            AssertionError: If no inner field names are defined.
            AttributeError: If a sub-field is not loaded and the instance is not
                            fully loaded or deleted.
        """
        # Ensure there is at least one inner field name.
        assert len(self.inner_field_names) >= 1

        # Handle ConditionalRedirect model and single inner field.
        if self.model is ConditionalRedirect and len(self.inner_field_names) == 1:
            try:
                return getattr(instance, self.inner_field_names[0])
            except AttributeError:
                # If the instance is not loaded or deleted, raise AttributeError.
                if not instance._db_loaded_or_deleted:
                    raise AttributeError("not loaded") from None
                return None

        # If the MODEL_GETATTR_BEHAVIOR is "coro", delegate to the asynchronous getter.
        if MODEL_GETATTR_BEHAVIOR.get() == "coro":
            return self.aget(instance, owner=owner)

        d = {}
        # Synchronously retrieve sub-field values.
        for key in self.inner_field_names:
            translated_name = self.translate_name(key)
            try:
                d[translated_name] = getattr(instance, key)
            except (AttributeError, KeyError):
                # If the instance is not loaded or deleted, raise AttributeError.
                if not instance._db_loaded_or_deleted:
                    raise AttributeError("not loaded") from None
                pass  # Suppress error if already loaded/deleted.

        # If a Pydantic model is associated and it's not a ConditionalRedirect.
        if self.model is not None and self.model is not ConditionalRedirect:
            # If a fallback registry is already set, create the model directly.
            if FALLBACK_TARGET_REGISTRY.get() is not None:
                return self.model(**d)
            # Temporarily set the fallback registry to the owner's registry.
            token2 = FALLBACK_TARGET_REGISTRY.set(self.owner.meta.registry or None)
            try:
                return self.model(**d)
            finally:
                # Reset the fallback registry.
                FALLBACK_TARGET_REGISTRY.reset(token2)
        return d

    def clean(self, field_name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        """
        Cleans and prepares the value of the composite field's sub-fields.

        This method handles `ConditionalRedirect` models by delegating cleaning
        to the single inner field. Otherwise, it uses the base composite field's
        cleaning logic.

        Args:
            field_name: The name of the composite field.
            value: The value of the composite field (can be a dict, BaseModel, or other).
            for_query: A boolean indicating if the cleaning is for a query context.

        Returns:
            A dictionary containing the cleaned values of all sub-fields.

        Raises:
            AssertionError: If no inner field names are defined.
        """
        # Ensure there is at least one inner field name.
        assert len(self.inner_field_names) >= 1

        # If the model is ConditionalRedirect and there's a single inner field,
        # and the value is not already a dict or BaseModel, delegate to the
        # single field's clean method.
        if (
            self.model is ConditionalRedirect
            and len(self.inner_field_names) == 1
            and not isinstance(value, dict | BaseModel)
        ):
            field = self.owner.meta.fields[self.inner_field_names[0]]
            return field.clean(self.inner_field_names[0], value, for_query=for_query)
        # Otherwise, use the base composite field's cleaning method.
        return super().clean(field_name, value, for_query=for_query)

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        """
        Converts the raw value of the composite field into a format suitable
        for model instantiation.

        This method handles `ConditionalRedirect` models by delegating conversion
        to the single inner field. Otherwise, it uses the base composite field's
        conversion logic.

        Args:
            field_name: The name of the composite field.
            value: The raw value of the composite field.

        Returns:
            A dictionary containing the transformed values of all sub-fields.

        Raises:
            AssertionError: If no inner field names are defined.
        """
        # Ensure there is at least one inner field name.
        assert len(self.inner_field_names) >= 1

        # If the model is ConditionalRedirect and there's a single inner field,
        # and the value is not already a dict or BaseModel, delegate to the
        # single field's to_model method.
        if (
            self.model is ConditionalRedirect
            and len(self.inner_field_names) == 1
            and not isinstance(value, dict | BaseModel)
        ):
            field = self.owner.meta.fields[self.inner_field_names[0]]
            return field.to_model(self.inner_field_names[0], value)
        # Otherwise, use the base composite field's to_model method.
        return super().to_model(field_name, value)

    def get_embedded_fields(
        self, name: str, fields: dict[str, BaseFieldType]
    ) -> dict[str, BaseFieldType]:
        """
        Retrieves the fields that are to be embedded within this composite field.

        This method manages potential field collisions and ensures that embedded
        fields are properly copied and associated with the current owner.

        Args:
            name: The name of the composite field itself.
            fields: A dictionary of existing fields in the model being built.

        Returns:
            A dictionary of `BaseFieldType` instances representing the embedded fields.

        Raises:
            ValueError: If duplicate fields are found when absorption is not enabled,
                        or if absorption fails due to type mismatch.
        """
        retdict = {}
        # If absorb_existing_fields is False, handle duplicates.
        if not self.absorb_existing_fields:
            # If owner is None, it means it's an uninitialized embeddable or current class.
            if self.owner is None:
                # Find duplicate field names between embedded fields and existing fields
                # that do not yet have an owner (meaning they are not yet part of a concrete model).
                duplicate_fields = set(self.embedded_field_defs.keys()).intersection(
                    {k for k, v in fields.items() if v.owner is None}
                )
                if duplicate_fields:
                    raise ValueError(f"duplicate fields: {', '.join(duplicate_fields)}")
            # Iterate through embedded field definitions.
            for field_name, field in self.embedded_field_defs.items():
                existing_field = fields.get(field_name)
                # Skip if an existing field without an owner is found and this field has an owner.
                if existing_field is not None and existing_field.owner is None and self.owner:
                    continue
                # Create a copy of the embedded field.
                cloned_field = copy.copy(field)
                # Set the owner of the cloned field to the current owner.
                cloned_field.owner = self.owner
                # Mark the cloned field as not inheriting.
                cloned_field.inherit = False
                retdict[field_name] = cloned_field
            return retdict

        # If absorb_existing_fields is True, try to absorb existing fields.
        for field_name, field in self.embedded_field_defs.items():
            if field_name not in fields:
                # If the field does not exist, clone and add it.
                cloned_field = copy.copy(field)
                cloned_field.owner = self.owner
                cloned_field.inherit = False
                retdict[field_name] = cloned_field
            else:
                # If the field exists, attempt absorption.
                absorbed_field = fields[field_name]
                # Check for type compatibility during absorption.
                if not getattr(absorbed_field, "skip_absorption_check", False) and not issubclass(
                    absorbed_field.field_type, field.field_type
                ):
                    raise ValueError(
                        f'absorption failed: field "{field_name}" handle the type: '
                        f"{absorbed_field.field_type}, required: {field.field_type}"
                    )
        return retdict

    def get_composite_fields(self) -> dict[str, BaseFieldType]:
        """
        Returns a dictionary of the actual field objects that compose this
        composite field, resolved from the owner model's meta.

        Returns:
            A dictionary where keys are field names and values are the
            corresponding `BaseFieldType` instances.
        """
        # Return a dictionary mapping inner field names to their corresponding
        # field objects from the owner's meta.
        return {field: self.owner.meta.fields[field] for field in self.inner_field_names}

    def is_required(self) -> bool:
        """
        Indicates that a composite field is generally not "required" in the
        same sense as a single column, as its presence is often derived
        from its sub-fields or model structure.

        Returns:
            `False`, as composite fields are not typically considered required inputs.
        """
        return False

    def has_default(self) -> bool:
        """
        Indicates that a composite field does not typically have a direct
        default value, as defaults are managed by its individual sub-fields.

        Returns:
            `False`, as composite fields do not usually have a default value.
        """
        return False

    def __copy__(self) -> ConcreteCompositeField:
        """
        Creates a shallow copy of the `ConcreteCompositeField` instance.

        Ensures that the `embedded_field_defs` dictionary and its contained
        fields are also copied to prevent unintended shared state.

        Returns:
            A shallow copy of the `ConcreteCompositeField` instance.
        """
        # Create a dictionary of parameters for the new copy, excluding 'null'.
        params = {k: v for k, v in self.__dict__.items() if k != "null"}
        # Create a new instance of the same type.
        copy_obj = type(self)(**params)
        # Deep copy the embedded_field_defs to ensure independent field instances.
        copy_obj.embedded_field_defs = {
            k: copy.copy(v) for k, v in self.embedded_field_defs.items()
        }
        return copy_obj


class CompositeField(FieldFactory):
    """
    A factory for creating composite fields, which aggregate multiple fields
    into a single logical unit within a model.

    This factory ensures proper validation of `inner_fields` and determines
    the appropriate Pydantic type representation for the composite field.
    """

    field_bases = (ConcreteCompositeField,)

    @classmethod
    def get_pydantic_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Determines the Pydantic type representation for the composite field.

        If a 'model' is explicitly provided in `kwargs`, that model type is used.
        Otherwise, the composite field is represented as a `dict[str, Any]`.

        Args:
            kwargs: A dictionary of keyword arguments passed to the field definition.

        Returns:
            The Pydantic type to be used for the composite field.
        """
        # If 'model' is present in kwargs, return it as the Pydantic type.
        if "model" in kwargs:
            return kwargs.get("model")
        # Otherwise, the composite field is represented as a dictionary.
        return dict[str, Any]

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Validates the arguments provided for creating a composite field.

        This method checks the `inner_fields` argument to ensure it is correctly
        formatted (a sequence, dictionary, or model) and not empty. It also
        validates the `model` argument if provided.

        Args:
            kwargs: A dictionary of keyword arguments passed to the field definition.

        Raises:
            FieldDefinitionError: If `inner_fields` is invalid (e.g., empty,
                                  incorrect type, or contains duplicates), or
                                  if `model` is not a valid type.
        """
        inner_fields = kwargs.get("inner_fields")
        if inner_fields is not None:
            # If inner_fields is a model with a 'meta' attribute, extract its fields.
            if hasattr(inner_fields, "meta"):
                kwargs.setdefault("model", inner_fields)
                inner_fields = inner_fields.meta.fields
            # If inner_fields is a dictionary, convert it to an items view.
            if isinstance(inner_fields, dict):
                inner_fields = inner_fields.items()
            # If it's not a sequence, raise an error.
            elif not isinstance(inner_fields, Sequence):
                raise FieldDefinitionError("inner_fields must be a Sequence, a dict or a model")
            # If inner_fields is empty, raise an error.
            if not inner_fields:
                raise FieldDefinitionError("inner_fields mustn't be empty")

            inner_field_names: set[str] = set()
            # Iterate through inner fields to check for duplicates.
            for field in inner_fields:
                if isinstance(field, str):
                    if field in inner_field_names:
                        raise FieldDefinitionError(f"duplicate inner field {field}")
                    inner_field_names.add(field)
                else:
                    if field[0] in inner_field_names:
                        raise FieldDefinitionError(f"duplicate inner field {field[0]}")
                    inner_field_names.add(field[0])

        model = kwargs.get("model")
        # If a model is provided, ensure it is a type.
        if model is not None and not isinstance(model, type):
            raise FieldDefinitionError(f"model must be type {model}")
