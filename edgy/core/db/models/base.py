from __future__ import annotations

import copy
import inspect
import warnings
from collections.abc import Sequence
from functools import cached_property
from typing import TYPE_CHECKING, Any, ClassVar, cast

from pydantic import BaseModel, ConfigDict, PrivateAttr

from edgy.core.db.context_vars import (
    CURRENT_FIELD_CONTEXT,
    CURRENT_INSTANCE,
    CURRENT_MODEL_INSTANCE,
    CURRENT_PHASE,
    MODEL_GETATTR_BEHAVIOR,
)
from edgy.core.db.models.model_reference import ModelRef
from edgy.core.utils.sync import run_sync
from edgy.types import Undefined

from .types import BaseModelType

if TYPE_CHECKING:
    from edgy.core.connection.database import Database
    from edgy.core.db.fields.types import FIELD_CONTEXT_TYPE, BaseFieldType
    from edgy.core.db.models.model import Model
    from edgy.core.db.querysets.base import QuerySet


_empty = cast(set[str], frozenset())
_excempted_attrs: set[str] = {
    "_db_loaded",
    "_db_deleted",
    "_edgy_namespace",
    "_edgy_private_attrs",
}


class EdgyBaseModel(BaseModel, BaseModelType):
    model_config = ConfigDict(
        extra="allow", arbitrary_types_allowed=True, validate_assignment=True
    )

    _edgy_private_attrs: ClassVar[set[str]] = PrivateAttr(
        default={
            "__show_pk__",
            "__using_schema__",
            "__no_load_trigger_attrs__",
            "__deletion_with_signals__",
            "database",
            "transaction",
        }
    )
    _edgy_namespace: dict = PrivateAttr()
    __proxy_model__: ClassVar[type[Model] | None] = None
    __reflected__: ClassVar[bool] = False
    __show_pk__: ClassVar[bool] = False
    __using_schema__: ClassVar[str | None | Any] = Undefined
    __deletion_with_signals__: ClassVar[bool] = False
    __no_load_trigger_attrs__: ClassVar[set[str]] = _empty
    database: ClassVar[Database] = None
    # private attributes
    _db_loaded: bool = PrivateAttr(default=False)
    # not in db anymore or deleted
    _db_deleted: bool = PrivateAttr(default=False)
    _db_schemas: ClassVar[dict[str, type[BaseModelType]]]

    def __init__(
        self,
        *args: Any,
        __show_pk__: bool | None = None,
        __phase__: str = "init",
        __drop_extra_kwargs__: bool = False,
        **kwargs: Any,
    ) -> None:
        """
        Initializes the EdgyBaseModel instance.

        Sets up private attributes, handles ModelRef instances for relationships,
        transforms input keyword arguments, and initializes Pydantic BaseModel.

        :param args: Positional arguments, can include ModelRef instances.
        :param __show_pk__: Flag to control primary key visibility.
        :param __phase__: The current phase of model initialization (e.g., "init").
        :param __drop_extra_kwargs__: If True, extra kwargs not defined in model fields
                                       will be dropped.
        :param kwargs: Keyword arguments for model fields.
        """
        # Always set _db_loaded and _db_deleted in __dict__ to prevent __getattr__ loop.
        self.__dict__["_db_loaded"] = False
        self.__dict__["_db_deleted"] = False
        klass = self.__class__
        # Initialize _edgy_namespace with class-level private attribute values.
        self.__dict__["_edgy_namespace"] = _edgy_namespace = {
            "__show_pk__": klass.__show_pk__,
            "__no_load_trigger_attrs__": {*klass.__no_load_trigger_attrs__},
            "__using_schema__": klass.__using_schema__,
            "__deletion_with_signals__": klass.__deletion_with_signals__,
            "database": klass.database,
        }
        # Override __show_pk__ if provided in kwargs.
        if __show_pk__ is not None:
            self.__show_pk__ = __show_pk__

        # Handle ModelRef instances for relation fields.
        for arg in args:
            if isinstance(arg, ModelRef):
                # Retrieve the relation field based on __related_name__.
                relation_field = self.meta.fields[arg.__related_name__]
                extra_params = {}
                try:
                    # Determine the target model class for m2m or foreign key.
                    target_model_class = relation_field.target
                except AttributeError:
                    # Determine the target model class for reverse m2m or foreign key.
                    target_model_class = relation_field.related_from
                # If not a many-to-many relationship, set the foreign key.
                if not relation_field.is_m2m:
                    extra_params[relation_field.foreign_key.name] = self
                # Create the model instance from ModelRef and extra parameters.
                model = target_model_class(
                    **arg.model_dump(exclude={"__related_name__"}),
                    **extra_params,
                )
                existing: Any = kwargs.get(arg.__related_name__)
                # Append or set the model in kwargs for the relation field.
                if isinstance(existing, Sequence):
                    existing = [*existing, model]
                elif existing is None:
                    existing = [model]
                else:
                    existing = [existing, model]
                kwargs[arg.__related_name__] = existing

        # Transform input kwargs before Pydantic initialization.
        kwargs = self.transform_input(
            kwargs,
            phase=__phase__,
            instance=self,
            drop_extra_kwargs=__drop_extra_kwargs__,
        )
        # Remove temporary _db_loaded and _db_deleted from __dict__ before super().__init__.
        del self.__dict__["_edgy_namespace"]
        _db_loaded = self.__dict__.pop("_db_loaded")
        _db_deleted = self.__dict__.pop("_db_deleted")
        # Call Pydantic BaseModel's __init__.
        super().__init__(**kwargs)
        # Re-set _db_loaded and _db_deleted properly after Pydantic initialization.
        self._db_loaded = _db_loaded
        self._db_deleted = _db_deleted
        self._edgy_namespace = _edgy_namespace
        # Move Pydantic extra attributes to __dict__.
        if self.__pydantic_extra__ is not None:
            self.__dict__.update(self.__pydantic_extra__)
            self.__pydantic_extra__ = None

        # Clean up fields not present in kwargs from __dict__.
        for field_name in self.meta.fields:
            if field_name not in kwargs:
                self.__dict__.pop(field_name, None)

    @property
    def _db_loaded_or_deleted(self) -> bool:
        """
        Indicates if the model instance is loaded from the database or marked as deleted.

        :return: True if loaded or deleted, False otherwise.
        """
        return self._db_loaded or self._db_deleted

    @property
    def _loaded_or_deleted(self) -> bool:
        """
        Deprecated: Use `_db_loaded_or_deleted` instead.

        Indicates if the model instance is loaded from the database or marked as deleted.

        :return: True if loaded or deleted, False otherwise.
        """
        warnings.warn(
            '"_loaded_or_deleted" is deprecated use "_db_loaded_or_deleted" instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        return self._db_loaded_or_deleted

    @classmethod
    def transform_input(
        cls,
        kwargs: dict[str, Any],
        phase: str = "",
        instance: BaseModelType | None = None,
        drop_extra_kwargs: bool = False,
    ) -> Any:
        """
        Transforms input keyword arguments by applying field-specific modifications
        and `to_model` transformations.

        :param kwargs: The input keyword arguments to transform.
        :param phase: The current phase of transformation.
        :param instance: The model instance being transformed.
        :param drop_extra_kwargs: If True, extra kwargs not defined in model fields
                                   will be dropped.
        :return: The transformed keyword arguments.
        """

        # Create a copy of kwargs to avoid modifying the original input.
        kwargs = kwargs.copy()
        new_kwargs: dict[str, Any] = {}

        fields = cls.meta.fields
        # Set context variables for the current instance, model instance, and phase.
        token = CURRENT_INSTANCE.set(instance)
        token2 = CURRENT_MODEL_INSTANCE.set(instance)
        token3 = CURRENT_PHASE.set(phase)
        try:
            # Phase 1: Apply input modifying fields.
            for field_name in cls.meta.input_modifying_fields:
                fields[field_name].modify_input(field_name, kwargs)
            # Phase 2: Apply `to_model` transformations.
            for key, value in kwargs.items():
                field = fields.get(key, None)
                if field is not None:
                    # If a field exists, apply its to_model transformation.
                    new_kwargs.update(**field.to_model(key, value))
                elif not drop_extra_kwargs:
                    # If no field and not dropping extra kwargs, keep the value.
                    new_kwargs[key] = value
        finally:
            # Reset context variables.
            CURRENT_PHASE.reset(token3)
            CURRENT_MODEL_INSTANCE.reset(token2)
            CURRENT_INSTANCE.reset(token)
        return new_kwargs

    def join_identifiers_to_string(self, *, sep: str = ", ", sep_inner: str = "=") -> str:
        """
        Joins the identifying database fields and their values into a string.

        :param sep: Separator for multiple identifier-value pairs.
        :param sep_inner: Separator between identifier and its value.
        :return: A string representation of identifying fields.
        """
        pkl = []
        # Set MODEL_GETATTR_BEHAVIOR to "passdown" to prevent triggering loads.
        token = MODEL_GETATTR_BEHAVIOR.set("passdown")
        try:
            for identifier in self.identifying_db_fields:
                # Append identifier and its value to the list.
                pkl.append(f"{identifier}{sep_inner}{getattr(self, identifier, None)}")
        except AttributeError:
            # Handle abstract embedded cases where identifiers might not be directly available.
            pass
        finally:
            # Reset MODEL_GETATTR_BEHAVIOR.
            MODEL_GETATTR_BEHAVIOR.reset(token)
        return sep.join(pkl)

    def __repr__(self) -> str:
        """
        Returns the official string representation of the model instance.

        :return: A string representation.
        """
        return f"<{type(self).__name__}: {self}>"

    def __str__(self) -> str:
        """
        Returns the informal string representation of the model instance,
        typically used for display.

        :return: A string representation including identifying fields.
        """
        return f"{type(self).__name__}({self.join_identifiers_to_string()})"

    @cached_property
    def identifying_db_fields(self) -> Any:
        """
        Returns the columns used for loading the model instance.
        Defaults to primary key columns.
        """
        return self.pkcolumns

    @property
    def proxy_model(self) -> type[Model]:
        """
        Returns the proxy model associated with this instance's class.
        """
        return type(self).proxy_model  # type: ignore

    @property
    def can_load(self) -> bool:
        """
        Checks if the model instance can be loaded from the database.
        Requires a registry, not to be abstract, and all identifying fields to have values.

        :return: True if the model can be loaded, False otherwise.
        """
        return bool(
            self.meta.registry
            and not self.meta.abstract
            and all(self.__dict__.get(field) is not None for field in self.identifying_db_fields)
        )

    async def load_recursive(
        self,
        only_needed: bool = False,
        only_needed_nest: bool = False,
        _seen: set[Any] | None = None,
    ) -> None:
        """
        Recursively loads related model instances.

        :param only_needed: If True, only load if the instance is not already loaded.
        :param only_needed_nest: If True, stop recursion for nested instances if already loaded.
        :param _seen: A set of seen model keys to prevent infinite recursion.
        """
        # Initialize _seen set if not provided.
        if _seen is None:
            _seen = {self.create_model_key()}
        else:
            model_key = self.create_model_key()
            # If the model key has been seen, return to prevent infinite recursion.
            if model_key in _seen:
                return
            else:
                _seen.add(model_key)
        _db_loaded_or_deleted = self._db_loaded_or_deleted
        # Load the current instance if it can be loaded.
        if self.can_load:
            await self.load(only_needed)
        # If only_needed_nest is True and the instance is already loaded or deleted, return.
        if only_needed_nest and _db_loaded_or_deleted:
            return
        # Recursively load foreign key fields.
        for field_name in self.meta.foreign_key_fields:
            value = getattr(self, field_name, None)
            if value is not None:
                # If a subinstance is fully loaded, stop further loading for it.
                await value.load_recursive(
                    only_needed=only_needed, only_needed_nest=True, _seen=_seen
                )

    @property
    def signals(self) -> Any:
        """
        Deprecated: Use `meta.signals` instead.

        Returns the broadcaster for signals.
        """
        warnings.warn(
            "'signals' has been deprecated, use 'meta.signals' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.meta.signals

    @property
    def fields(self) -> dict[str, BaseFieldType]:
        """
        Deprecated: Use `meta.fields` instead.

        Returns a dictionary of the model's fields.
        """
        warnings.warn(
            "'fields' has been deprecated, use 'meta.fields' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.meta.fields

    async def execute_pre_save_hooks(
        self, column_values: dict[str, Any], original: dict[str, Any], is_update: bool
    ) -> dict[str, Any]:
        """
        Executes pre-save hooks for relevant fields.

        :param column_values: Dictionary of new column values.
        :param original: Dictionary of original column values.
        :param is_update: True if the operation is an update, False for creation.
        :return: A dictionary of values returned by pre-save callbacks.
        """
        # also handle defaults
        # Combine keys from new and original column values to identify affected fields.
        keys = {*column_values.keys(), *original.keys()}
        affected_fields = self.meta.pre_save_fields.intersection(keys)
        retdict: dict[str, Any] = {}
        if affected_fields:
            # Set MODEL_GETATTR_BEHAVIOR to "passdown" to prevent triggering loads.
            token = MODEL_GETATTR_BEHAVIOR.set("passdown")
            token2 = CURRENT_MODEL_INSTANCE.set(self)
            field_dict: FIELD_CONTEXT_TYPE = cast("FIELD_CONTEXT_TYPE", {})
            token_field_ctx = CURRENT_FIELD_CONTEXT.set(field_dict)
            try:
                for field_name in affected_fields:
                    # Skip if the field is not in new or original values.
                    if field_name not in column_values and field_name not in original:
                        continue
                    field = self.meta.fields[field_name]
                    field_dict.clear()
                    field_dict["field"] = field
                    # Execute pre-save callback for the field.
                    retdict.update(
                        await field.pre_save_callback(
                            column_values.get(field_name),
                            original.get(field_name),
                            is_update=is_update,
                        )
                    )
            finally:
                # Reset context variables.
                CURRENT_FIELD_CONTEXT.reset(token_field_ctx)
                MODEL_GETATTR_BEHAVIOR.reset(token)
                CURRENT_MODEL_INSTANCE.reset(token2)
        return retdict

    async def execute_post_save_hooks(self, fields: Sequence[str], is_update: bool) -> None:
        """
        Executes post-save hooks for relevant fields.

        :param fields: A sequence of field names that were affected by the save operation.
        :param is_update: True if the operation was an update, False for creation.
        """
        # Determine affected fields by intersecting with post-save fields.
        affected_fields = self.meta.post_save_fields.intersection(fields)
        if affected_fields:
            # Set MODEL_GETATTR_BEHAVIOR to "passdown" to prevent triggering loads.
            token = MODEL_GETATTR_BEHAVIOR.set("passdown")
            token2 = CURRENT_MODEL_INSTANCE.set(self)
            field_dict: FIELD_CONTEXT_TYPE = cast("FIELD_CONTEXT_TYPE", {})
            token_field_ctx = CURRENT_FIELD_CONTEXT.set(field_dict)
            try:
                for field_name in affected_fields:
                    field = self.meta.fields[field_name]
                    try:
                        # Attempt to get the field value.
                        value = getattr(self, field_name)
                    except AttributeError:
                        # Skip if the attribute is not found.
                        continue
                    field_dict.clear()
                    field_dict["field"] = field
                    # Execute post-save callback for the field.
                    await field.post_save_callback(value, is_update=is_update)
            finally:
                # Reset context variables.
                CURRENT_FIELD_CONTEXT.reset(token_field_ctx)
                MODEL_GETATTR_BEHAVIOR.reset(token)
                CURRENT_MODEL_INSTANCE.reset(token2)

    @classmethod
    def extract_column_values(
        cls,
        extracted_values: dict[str, Any],
        is_update: bool = False,
        is_partial: bool = False,
        phase: str = "",
        instance: BaseModelType | QuerySet | None = None,
        model_instance: BaseModelType | None = None,
        evaluate_values: bool = False,
    ) -> dict[str, Any]:
        """
        Extracts and validates column values, applying transformations and defaults.

        :param extracted_values: Dictionary of values to extract and validate.
        :param is_update: True if the operation is an update.
        :param is_partial: True if it's a partial update/creation.
        :param phase: The current phase of extraction.
        :param instance: The current instance being processed.
        :param model_instance: The model instance context.
        :param evaluate_values: If True, callable values in `extracted_values` will be
                                 evaluated.
        :return: A dictionary of validated column values.
        """
        validated: dict[str, Any] = {}
        # Set context variables for phase, current instance, and model instance.
        token = CURRENT_PHASE.set(phase)
        token2 = CURRENT_INSTANCE.set(instance)
        token3 = CURRENT_MODEL_INSTANCE.set(model_instance)
        field_dict: FIELD_CONTEXT_TYPE = cast("FIELD_CONTEXT_TYPE", {})
        token_field_ctx = CURRENT_FIELD_CONTEXT.set(field_dict)

        try:
            # Phase 1: Evaluate callable values if `evaluate_values` is True.
            if evaluate_values:
                new_extracted_values = {}
                for k, v in extracted_values.items():
                    if callable(v):
                        field_dict.clear()
                        field_dict["field"] = cast("BaseFieldType", cls.meta.fields.get(k))
                        v = v()
                    new_extracted_values[k] = v
                extracted_values = new_extracted_values
            else:
                extracted_values = {**extracted_values}
            # Phase 2: Apply input modifying fields.
            if cls.meta.input_modifying_fields:
                for field_name in cls.meta.input_modifying_fields:
                    cls.meta.fields[field_name].modify_input(field_name, extracted_values)
            # Phase 3: Validate fields and set defaults for read-only fields.
            need_second_pass: list[BaseFieldType] = []
            for field_name, field in cls.meta.fields.items():
                field_dict.clear()
                field_dict["field"] = field
                if field.read_only:
                    # If read-only, and not a partial update or inject_default_on_partial_update,
                    # and has a default, apply default values.
                    if (
                        not is_partial or (field.inject_default_on_partial_update and is_update)
                    ) and field.has_default():
                        validated.update(field.get_default_values(field_name, validated))
                    continue
                if field_name in extracted_values:
                    item = extracted_values[field_name]
                    assert field.owner
                    # Clean and update validated values.
                    for sub_name, value in field.clean(field_name, item).items():
                        if sub_name in validated:
                            raise ValueError(f"value set twice for key: {sub_name}")
                        validated[sub_name] = value
                elif (
                    not is_partial or (field.inject_default_on_partial_update and is_update)
                ) and field.has_default():
                    # Add fields with defaults to a second pass if not partial
                    # or if inject_default_on_partial_update is set for updates.
                    need_second_pass.append(field)

            # Phase 4: Set defaults for remaining fields if necessary.
            if need_second_pass:
                for field in need_second_pass:
                    field_dict.clear()
                    field_dict["field"] = field
                    # Check if field appeared (e.g., by composite) before setting default.
                    if field.name not in validated:
                        validated.update(field.get_default_values(field.name, validated))
        finally:
            # Reset context variables.
            CURRENT_FIELD_CONTEXT.reset(token_field_ctx)
            CURRENT_MODEL_INSTANCE.reset(token3)
            CURRENT_INSTANCE.reset(token2)
            CURRENT_PHASE.reset(token)
        return validated

    def __setattr__(self, key: str, value: Any) -> None:
        """
        Custom setter for model attributes.

        Handles private attributes, field transformations (`to_model`),
        and regular Pydantic model field assignments.

        :param key: The name of the attribute to set.
        :param value: The value to set.
        """
        # Handle Edgy's private attributes by storing them in _edgy_namespace.
        if key in self._edgy_private_attrs:
            self._edgy_namespace[key] = value
            return
        # Handle Pydantic's private attributes directly.
        if key in self.__private_attributes__:
            super().__setattr__(key, value)
            return

        fields = self.meta.fields
        field = fields.get(key, None)
        # Set context variables for the current instance, model instance, and phase.
        token = CURRENT_INSTANCE.set(self)
        token2 = CURRENT_MODEL_INSTANCE.set(self)
        token3 = CURRENT_PHASE.set("set")
        if field is not None:
            token_field_ctx = CURRENT_FIELD_CONTEXT.set(
                cast("FIELD_CONTEXT_TYPE", {"field": field})
            )
        try:
            if field is not None:
                # If the field has a custom __set__ method, use it.
                if hasattr(field, "__set__"):
                    field.__set__(self, value)
                else:
                    # Apply to_model transformation and set values.
                    for k, v in field.to_model(key, value).items():
                        if k in type(self).model_fields:
                            # If it's a Pydantic model field, use super().__setattr__.
                            super().__setattr__(k, v)
                        else:
                            # Otherwise, bypass __setattr__ to update __dict__ directly.
                            object.__setattr__(self, k, v)
            elif key in type(self).model_fields:
                # If it's a Pydantic model field, use super().__setattr__.
                super().__setattr__(key, value)
            else:
                # For other attributes, bypass __setattr__ to update __dict__ directly.
                object.__setattr__(self, key, value)
        finally:
            # Reset context variables.
            if field is not None:
                CURRENT_FIELD_CONTEXT.reset(token_field_ctx)
            CURRENT_INSTANCE.reset(token)
            CURRENT_MODEL_INSTANCE.reset(token2)
            CURRENT_PHASE.reset(token3)

    async def _agetattr_helper(self, name: str, getter: Any) -> Any:
        """
        Asynchronous helper for __getattr__ to load the model and retrieve attributes.

        :param name: The name of the attribute to retrieve.
        :param getter: The getter method for the attribute, if available.
        :return: The value of the attribute.
        :raises AttributeError: If the attribute is not found.
        """
        # Load the model data asynchronously.
        await self.load()
        if getter is not None:
            # If a getter is provided, use it, handling awaitable results.
            token = MODEL_GETATTR_BEHAVIOR.set("coro")
            try:
                result = getter(self, self.__class__)
                if inspect.isawaitable(result):
                    result = await result
                return result
            finally:
                MODEL_GETATTR_BEHAVIOR.reset(token)
        try:
            # Attempt to retrieve from __dict__.
            return self.__dict__[name]
        except KeyError:
            raise AttributeError(f"Attribute: {name} not found") from None

    def __getattribute__(self, name: str) -> Any:
        """
        Custom getter for model attributes.

        Handles retrieving Edgy's private attributes from `_edgy_namespace`.

        :param name: The name of the attribute to retrieve.
        :return: The value of the attribute.
        :raises AttributeError: If the attribute is not found in private namespace.
        """
        # If the attribute is an Edgy private attribute and not the private attributes set itself,
        # try to retrieve it from _edgy_namespace.
        if name != "_edgy_private_attrs" and name in self._edgy_private_attrs:
            try:
                return self._edgy_namespace[name]
            except KeyError as exc:
                raise AttributeError from exc
        # For all other attributes, use the default __getattribute__ behavior.
        return super().__getattribute__(name)

    def __getattr__(self, name: str) -> Any:
        """
        Custom getter for model attributes when not found through normal lookup.

        This method handles:
        1. Initialization of managers on first access.
        2. Redirection of attribute access to getter fields.
        3. Triggering a one-off database query to populate foreign key relationships,
           ensuring it runs only once per foreign key.

        :param name: The name of the attribute to retrieve.
        :return: The value of the attribute.
        """
        # Attributes exempted from triggering special __getattr__ logic.
        if name in _excempted_attrs or name in self._edgy_private_attrs:
            return super().__getattr__(name)

        behavior = MODEL_GETATTR_BEHAVIOR.get()
        manager = self.meta.managers.get(name)
        if manager is not None:
            # Initialize and cache manager instances on first access.
            if name not in self._edgy_namespace:
                manager = copy.copy(manager)
                manager.instance = self
                self._edgy_namespace[name] = manager
            return self._edgy_namespace[name]

        field = self.meta.fields.get(name)
        if field is not None:
            token_field_ctx = CURRENT_FIELD_CONTEXT.set(
                cast("FIELD_CONTEXT_TYPE", {"field": field})
            )
        try:
            getter: Any = None
            if field is not None and hasattr(field, "__get__"):
                getter = field.__get__
                # If behavior is "coro" or "passdown", return the getter result directly.
                if behavior == "coro" or behavior == "passdown":
                    return field.__get__(self, self.__class__)
                else:
                    # Otherwise, set "passdown" behavior and try to get the field value.
                    token = MODEL_GETATTR_BEHAVIOR.set("passdown")
                    try:
                        return field.__get__(self, self.__class__)
                    except AttributeError:
                        # If AttributeError, forward to the load routine.
                        pass
                    finally:
                        MODEL_GETATTR_BEHAVIOR.reset(token)
            # If the attribute is not in __dict__, not in "passdown" behavior,
            # not already loaded/deleted, and is a loadable field, trigger a load.
            if (
                name not in self.__dict__
                and behavior != "passdown"
                # is already loaded or deleted
                and not self._db_loaded_or_deleted
                # only load when it is a field except for reflected
                and (field is not None or self.__reflected__)
                # exclude attr names from triggering load
                and name not in getattr(self, "__no_load_trigger_attrs__", _empty)
                and name not in self.identifying_db_fields
                and self.can_load
            ):
                coro = self._agetattr_helper(name, getter)
                # If behavior is "coro", return the coroutine directly.
                if behavior == "coro":
                    return coro
                # Otherwise, run the coroutine synchronously.
                return run_sync(coro)
            # If none of the above, use the default __getattr__ behavior (will raise AttributeError).
            return super().__getattr__(name)
        finally:
            # Reset CURRENT_FIELD_CONTEXT if a field was involved.
            if field:
                CURRENT_FIELD_CONTEXT.reset(token_field_ctx)

    def __delattr__(self, name: str) -> None:
        """
        Custom deleter for model attributes.

        Handles deleting Edgy's private attributes from `_edgy_namespace`.

        :param name: The name of the attribute to delete.
        :raises AttributeError: If the attribute is not found in private namespace.
        """
        # If the attribute is an Edgy private attribute, try to delete it from _edgy_namespace.
        if name in self._edgy_private_attrs:
            try:
                del self._edgy_namespace[name]
                return
            except KeyError as exc:
                raise AttributeError from exc
        # For all other attributes, use the default __delattr__ behavior.
        super().__delattr__(name)

    def __eq__(self, other: Any) -> bool:
        """
        Compares two EdgyBaseModel instances for equality.

        Equality is determined by comparing their table name, registry,
        and the values of their identifying database fields.

        :param other: The other object to compare with.
        :return: True if the instances are equal, False otherwise.
        """
        # If the other object is not an instance of EdgyBaseModel, they are not equal.
        if not isinstance(other, EdgyBaseModel):
            return False
        # Compare registry and table name for quick inequality checks.
        if self.meta.registry is not other.meta.registry:
            return False
        if self.meta.tablename != other.meta.tablename:
            return False

        # Extract identifying column values for comparison, handling partial extraction.
        self_dict = self.extract_column_values(
            self.extract_db_fields(self.pkcolumns),
            is_partial=True,
            phase="compare",
            instance=self,
            model_instance=self,
        )
        other_dict = other.extract_column_values(
            other.extract_db_fields(self.pkcolumns),
            is_partial=True,
            phase="compare",
            instance=other,
            model_instance=other,
        )
        # Get all unique keys from both dictionaries.
        key_set = {*self_dict.keys(), *other_dict.keys()}
        # Compare values for each key. If any mismatch, return False.
        for field_name in key_set:
            if self_dict.get(field_name) != other_dict.get(field_name):
                return False
        # If all identifying field values match, the instances are considered equal.
        return True
