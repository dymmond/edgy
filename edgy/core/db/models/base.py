from __future__ import annotations

import copy
import inspect
import warnings
from collections.abc import Sequence
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Literal,
    Optional,
    Union,
    cast,
)

import orjson
from pydantic import BaseModel, ConfigDict
from pydantic_core._pydantic_core import SchemaValidator as SchemaValidator

from edgy.core.db.context_vars import (
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
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.model import Model
    from edgy.core.db.querysets.base import QuerySet
    from edgy.core.signals import Broadcaster

_empty = cast(set[str], frozenset())


class EdgyBaseModel(BaseModel, BaseModelType):
    """
    Base of all Edgy models with the core setup.
    """

    # when used with marshalls: marshalls can dump unrelated informations which must be ignored
    # so it isn't possible to use forbid yet, despite it would show bugs in code
    model_config = ConfigDict(
        extra="ignore", arbitrary_types_allowed=True, validate_assignment=True
    )

    __proxy_model__: ClassVar[Union[type[Model], None]] = None
    __reflected__: ClassVar[bool] = False
    __show_pk__: ClassVar[bool] = False
    __using_schema__: Union[str, None, Any] = Undefined
    # private attribute
    database: ClassVar[Database] = None
    _loaded_or_deleted: bool = False

    def __init__(
        self, *args: Any, __show_pk__: bool = False, __phase__: str = "init", **kwargs: Any
    ) -> None:
        self.__show_pk__ = __show_pk__
        # always set them in __dict__ to prevent __getattr__ loop
        self._loaded_or_deleted = False
        # inject in relation fields anonymous ModelRef (without a Field)
        for arg in args:
            if isinstance(arg, ModelRef):
                relation_field = self.meta.fields[arg.__related_name__]
                extra_params = {}
                try:
                    # m2m or foreign key
                    target_model_class = relation_field.target
                except AttributeError:
                    # reverse m2m or foreign key
                    target_model_class = relation_field.related_from
                if not relation_field.is_m2m:
                    # sometimes the foreign key is required, so set it already
                    extra_params[relation_field.foreign_key.name] = self
                model = target_model_class(
                    **arg.model_dump(exclude={"__related_name__"}),
                    **extra_params,
                )
                existing: Any = kwargs.get(arg.__related_name__)
                if isinstance(existing, Sequence):
                    existing = [*existing, model]
                elif existing is None:
                    existing = [model]
                else:
                    existing = [existing, model]
                kwargs[arg.__related_name__] = existing

        kwargs = self.transform_input(kwargs, phase=__phase__, instance=self)
        super().__init__(**kwargs)
        # move to dict (e.g. reflected or subclasses which allow extra attributes)
        if self.__pydantic_extra__ is not None:
            # default was triggered
            self.__dict__.update(self.__pydantic_extra__)
            self.__pydantic_extra__ = None

        # cleanup fields
        for field_name in self.meta.fields:
            if field_name not in kwargs:
                self.__dict__.pop(field_name, None)

    @classmethod
    def transform_input(
        cls,
        kwargs: Any,
        phase: str = "",
        instance: Optional[BaseModelType] = None,
    ) -> Any:
        """
        Expand to_models and apply input modifications.
        """

        kwargs = {**kwargs}
        new_kwargs: dict[str, Any] = {}

        fields = cls.meta.fields
        token = CURRENT_INSTANCE.set(instance)
        token2 = CURRENT_MODEL_INSTANCE.set(instance)
        token3 = CURRENT_PHASE.set(phase)
        try:
            # phase 1: transform
            # Note: this is order dependend. There should be no overlap.
            for field_name in cls.meta.input_modifying_fields:
                fields[field_name].modify_input(field_name, kwargs)
            # phase 2: apply to_model
            for key, value in kwargs.items():
                field = fields.get(key, None)
                if field is not None:
                    new_kwargs.update(**field.to_model(key, value))
                else:
                    new_kwargs[key] = value
        finally:
            CURRENT_PHASE.reset(token3)
            CURRENT_MODEL_INSTANCE.reset(token2)
            CURRENT_INSTANCE.reset(token)
        return new_kwargs

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {str(self)}>"

    def __str__(self) -> str:
        pkl = []
        token = MODEL_GETATTR_BEHAVIOR.set("passdown")
        try:
            for identifier in self.identifying_db_fields:
                pkl.append(f"{identifier}={getattr(self, identifier, None)}")
        except AttributeError:
            # for abstract embedded
            pass
        finally:
            MODEL_GETATTR_BEHAVIOR.reset(token)
        return f"{self.__class__.__name__}({', '.join(pkl)})"

    @cached_property
    def identifying_db_fields(self) -> Any:
        """The columns used for loading, can be set per instance defaults to pknames"""
        return self.pkcolumns

    @cached_property
    def proxy_model(self) -> type[Model]:
        return self.__class__.proxy_model  # type: ignore

    @property
    def can_load(self) -> bool:
        return bool(
            self.meta.registry
            and not self.meta.abstract
            and all(self.__dict__.get(field) is not None for field in self.identifying_db_fields)
        )

    async def load_recursive(
        self,
        only_needed: bool = False,
        only_needed_nest: bool = False,
        _seen: Optional[set[Any]] = None,
    ) -> None:
        if _seen is None:
            _seen = {self.create_model_key()}
        else:
            model_key = self.create_model_key()
            if model_key in _seen:
                return
            else:
                _seen.add(model_key)
        _loaded_or_deleted = self._loaded_or_deleted
        if self.can_load:
            await self.load(only_needed)
        if only_needed_nest and _loaded_or_deleted:
            return
        for field_name in self.meta.foreign_key_fields:
            value = getattr(self, field_name, None)
            if value is not None:
                # if a subinstance is fully loaded stop
                await value.load_recursive(
                    only_needed=only_needed, only_needed_nest=True, _seen=_seen
                )

    @property
    def signals(self) -> Broadcaster:
        warnings.warn(
            "'signals' has been deprecated, use 'meta.signals' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.meta.signals

    @property
    def fields(self) -> dict[str, BaseFieldType]:
        warnings.warn(
            "'fields' has been deprecated, use 'meta.fields' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.meta.fields

    def model_dump(self, show_pk: Union[bool, None] = None, **kwargs: Any) -> dict[str, Any]:
        """
        An updated version of the model dump.
        It can show the pk always and handles the exclude attribute on fields correctly and
        contains the custom logic for fields with getters

        Extra Args:
            show_pk: bool - Enforces showing the primary key in the model_dump.
        """
        # we want a copy
        exclude: Union[set[str], dict[str, Any], None] = kwargs.pop("exclude", None)
        if exclude is None:
            initial_full_field_exclude = _empty
            # must be writable
            exclude = set()
        elif isinstance(exclude, dict):
            initial_full_field_exclude = {k for k, v in exclude.items() if v is True}
            exclude = copy.copy(exclude)
        else:
            initial_full_field_exclude = set(exclude)
            exclude = copy.copy(initial_full_field_exclude)

        if isinstance(exclude, dict):
            # exclude __show_pk__ attribute from showing up
            exclude["__show_pk__"] = True
            for field_name in self.meta.excluded_fields:
                exclude[field_name] = True
        else:
            exclude.update(self.meta.special_getter_fields)
            exclude.update(self.meta.excluded_fields)
            # exclude __show_pk__ attribute from showing up
            exclude.add("__show_pk__")
        include: Union[set[str], dict[str, Any], None] = kwargs.pop("include", None)
        mode: Union[Literal["json", "python"], str] = kwargs.pop("mode", "python")

        should_show_pk = self.__show_pk__ if show_pk is None else show_pk
        model = super().model_dump(exclude=exclude, include=include, mode=mode, **kwargs)
        # Workaround for metafields, computed field logic introduces many problems
        # so reimplement the logic here
        for field_name in self.meta.special_getter_fields:
            if field_name == "pk":
                continue
            if not should_show_pk or field_name not in self.pknames:
                if field_name in initial_full_field_exclude:
                    continue
                if include is not None and field_name not in include:
                    continue
                if getattr(field_name, "exclude", False):
                    continue
            field: BaseFieldType = self.meta.fields[field_name]
            try:
                retval = field.__get__(self, self.__class__)
            except AttributeError:
                continue
            sub_include = None
            if isinstance(include, dict):
                sub_include = include.get(field_name, None)
                if sub_include is True:
                    sub_include = None
            sub_exclude = None
            if isinstance(exclude, dict):
                sub_exclude = exclude.get(field_name, None)
                if sub_exclude is True:
                    sub_exclude = None
            if isinstance(retval, BaseModel):
                retval = retval.model_dump(
                    include=sub_include, exclude=sub_exclude, mode=mode, **kwargs
                )
            else:
                assert (
                    sub_include is None
                ), "sub include filters for CompositeField specified, but no Pydantic model is set"
                assert (
                    sub_exclude is None
                ), "sub exclude filters for CompositeField specified, but no Pydantic model is set"
                if mode == "json" and not getattr(field, "unsafe_json_serialization", False):
                    # skip field if it isn't a BaseModel and the mode is json and unsafe_json_serialization is not set
                    # currently unsafe_json_serialization exists only on CompositeFields
                    continue
            alias: str = field_name
            if getattr(field, "serialization_alias", None):
                alias = cast(str, field.serialization_alias)
            elif getattr(field, "alias", None):
                alias = field.alias
            model[alias] = retval
        # proxyModel? cause excluded fields to reappear
        # TODO: find a better bugfix
        for excluded_field in self.meta.excluded_fields:
            model.pop(excluded_field, None)
        return model

    def model_dump_json(self, **kwargs: Any) -> str:
        return orjson.dumps(self.model_dump(mode="json", **kwargs)).decode()

    async def execute_pre_save_hooks(
        self, column_values: dict[str, Any], original: dict[str, Any], force_insert: bool
    ) -> dict[str, Any]:
        # also handle defaults
        keys = {*column_values.keys(), *original.keys()}
        affected_fields = self.meta.pre_save_fields.intersection(keys)
        retdict: dict[str, Any] = {}
        if affected_fields:
            # don't trigger loads
            token = MODEL_GETATTR_BEHAVIOR.set("passdown")
            token2 = CURRENT_MODEL_INSTANCE.set(self)
            try:
                for field_name in affected_fields:
                    if field_name not in column_values and field_name not in original:
                        continue
                    field = self.meta.fields[field_name]
                    retdict.update(
                        await field.pre_save_callback(
                            column_values.get(field_name),
                            original.get(field_name),
                            force_insert=force_insert,
                            instance=self,
                        )
                    )
            finally:
                MODEL_GETATTR_BEHAVIOR.reset(token)
                CURRENT_MODEL_INSTANCE.reset(token2)
        return retdict

    async def execute_post_save_hooks(self, fields: Sequence[str], force_insert: bool) -> None:
        affected_fields = self.meta.post_save_fields.intersection(fields)
        if affected_fields:
            # don't trigger loads, AttributeErrors are used for skipping fields
            token = MODEL_GETATTR_BEHAVIOR.set("passdown")
            token2 = CURRENT_MODEL_INSTANCE.set(self)
            try:
                for field_name in affected_fields:
                    field = self.meta.fields[field_name]
                    try:
                        value = getattr(self, field_name)
                    except AttributeError:
                        continue
                    await field.post_save_callback(value, instance=self, force_insert=force_insert)
            finally:
                MODEL_GETATTR_BEHAVIOR.reset(token)
                CURRENT_MODEL_INSTANCE.reset(token2)

    @classmethod
    def extract_column_values(
        cls,
        extracted_values: dict[str, Any],
        is_update: bool = False,
        is_partial: bool = False,
        phase: str = "",
        instance: Optional[Union[BaseModelType, QuerySet]] = None,
        model_instance: Optional[BaseModelType] = None,
    ) -> dict[str, Any]:
        validated: dict[str, Any] = {}
        token = CURRENT_PHASE.set(phase)
        token2 = CURRENT_INSTANCE.set(instance)
        token3 = CURRENT_MODEL_INSTANCE.set(model_instance)
        try:
            # phase 1: transform when required
            if cls.meta.input_modifying_fields:
                extracted_values = {**extracted_values}
                for field_name in cls.meta.input_modifying_fields:
                    cls.meta.fields[field_name].modify_input(field_name, extracted_values)
            # phase 2: validate fields and set defaults for readonly
            need_second_pass: list[BaseFieldType] = []
            for field_name, field in cls.meta.fields.items():
                if field.read_only:
                    # if read_only, updates are not possible anymore
                    if (
                        not is_partial or (field.inject_default_on_partial_update and is_update)
                    ) and field.has_default():
                        validated.update(field.get_default_values(field_name, validated))
                    continue
                if field_name in extracted_values:
                    item = extracted_values[field_name]
                    assert field.owner
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
                    # Note: default values are directly passed without validation
                    if field.name not in validated:
                        validated.update(field.get_default_values(field.name, validated))
        finally:
            CURRENT_MODEL_INSTANCE.reset(token3)
            CURRENT_INSTANCE.reset(token2)
            CURRENT_PHASE.reset(token)
        return validated

    def __setattr__(self, key: str, value: Any) -> None:
        fields = self.meta.fields
        field = fields.get(key, None)
        token = CURRENT_INSTANCE.set(self)
        token2 = CURRENT_PHASE.set("set")
        try:
            if field is not None:
                if hasattr(field, "__set__"):
                    # not recommended, better to use to_model instead except for kept objects
                    # used in related_fields to mask and not to implement to_model
                    field.__set__(self, value)
                else:
                    for k, v in field.to_model(key, value).items():
                        if k in self.model_fields:
                            # __dict__ is updated and validator is executed
                            super().__setattr__(k, v)
                        else:
                            # bypass __setattr__ method
                            # ensures, __dict__ is updated
                            object.__setattr__(self, k, v)
            elif key in self.model_fields:
                # __dict__ is updated and validator is executed
                super().__setattr__(key, value)
            else:
                # bypass __setattr__ method
                # ensures, __dict__ is updated
                object.__setattr__(self, key, value)
        finally:
            CURRENT_INSTANCE.reset(token)
            CURRENT_PHASE.reset(token2)

    async def _agetattr_helper(self, name: str, getter: Any) -> Any:
        await self.load()
        if getter is not None:
            token = MODEL_GETATTR_BEHAVIOR.set("coro")
            try:
                result = getter(self, self.__class__)
                if inspect.isawaitable(result):
                    result = await result
                return result
            finally:
                MODEL_GETATTR_BEHAVIOR.reset(token)
        try:
            return self.__dict__[name]
        except KeyError:
            raise AttributeError(f"Attribute: {name} not found") from None

    def __getattr__(self, name: str) -> Any:
        """
        Does following things
        1. Initialize managers on access
        2. Redirects get accesses to getter fields
        3. Run an one off query to populate any foreign key making sure
           it runs only once per foreign key avoiding multiple database calls.
        """
        behavior = MODEL_GETATTR_BEHAVIOR.get()
        manager = self.meta.managers.get(name)
        if manager is not None:
            if name not in self.__dict__:
                manager = copy.copy(manager)
                manager.instance = self
                self.__dict__[name] = manager
            return self.__dict__[name]

        field = self.meta.fields.get(name)
        getter: Any = None
        if field is not None and hasattr(field, "__get__"):
            getter = field.__get__
            if behavior == "coro" or behavior == "passdown":
                return field.__get__(self, self.__class__)
            else:
                token = MODEL_GETATTR_BEHAVIOR.set("passdown")
                # no need to set an descriptor object
                try:
                    return field.__get__(self, self.__class__)
                except AttributeError:
                    # forward to load routine
                    pass
                finally:
                    MODEL_GETATTR_BEHAVIOR.reset(token)
        if (
            name not in self.__dict__
            and behavior != "passdown"
            and not self.__dict__.get("_loaded_or_deleted", False)
            and (field is not None or self.__reflected__)
            and name not in self.identifying_db_fields
            and self.can_load
        ):
            coro = self._agetattr_helper(name, getter)
            if behavior == "coro":
                return coro
            return run_sync(coro)
        return super().__getattr__(name)

    def __eq__(self, other: Any) -> bool:
        # if self.__class__ != other.__class__:
        #     return False
        # somehow meta gets regenerated, so just compare tablename and registry.
        if self.meta.registry is not other.meta.registry:
            return False
        if self.meta.tablename != other.meta.tablename:
            return False
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
        key_set = {*self_dict.keys(), *other_dict.keys()}
        for field_name in key_set:
            if self_dict.get(field_name) != other_dict.get(field_name):
                return False
        return True
