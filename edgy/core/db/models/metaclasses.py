from __future__ import annotations

import contextlib
import copy
import inspect
import warnings
from abc import ABCMeta
from collections import UserDict, deque
from collections.abc import Sequence
from contextvars import ContextVar
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Literal,
    Optional,
    Union,
    cast,
    get_origin,
)

import sqlalchemy
from pydantic._internal._model_construction import ModelMetaclass

from edgy.core import signals as signals_module
from edgy.core.connection.registry import Registry
from edgy.core.db import fields as edgy_fields
from edgy.core.db.datastructures import Index, UniqueConstraint
from edgy.core.db.fields.base import BaseForeignKey, PKField, RelationshipField
from edgy.core.db.fields.foreign_keys import BaseForeignKeyField
from edgy.core.db.fields.ref_foreign_key import BaseRefForeignKey
from edgy.core.db.fields.types import BaseFieldType
from edgy.core.db.models.managers import BaseManager
from edgy.core.db.models.utils import build_pkcolumns, build_pknames
from edgy.core.utils.functional import extract_field_annotations_and_defaults
from edgy.exceptions import ImproperlyConfigured, TableBuildError

if TYPE_CHECKING:
    from databasez.core.transaction import Transaction

    from edgy.core.connection import Database
    from edgy.core.db.models import Model
    from edgy.core.db.models.types import BaseModelType

_empty_dict: dict[str, Any] = {}
_empty_set: frozenset[Any] = frozenset()

_seen_table_names: ContextVar[set[str]] = ContextVar("_seen_table_names", default=None)


class Fields(UserDict, dict[str, BaseFieldType]):
    """Smart wrapper which tries to prevent invalidation as far as possible"""

    def __init__(self, meta: MetaInfo, data: Optional[dict[str, BaseFieldType]] = None):
        self.meta = meta
        super().__init__(data)

    def add_field_to_meta(self, name: str, field: BaseFieldType) -> None:
        if not self.meta._field_stats_are_initialized:
            return
        if hasattr(field, "__get__"):
            self.meta.special_getter_fields.add(name)
        if getattr(field, "exclude", False):
            self.meta.excluded_fields.add(name)
        if getattr(field, "secret", False):
            self.meta.secret_fields.add(name)
        if hasattr(field, "modify_input"):
            self.meta.input_modifying_fields.add(name)
        if hasattr(field, "post_save_callback"):
            self.meta.post_save_fields.add(name)
        if hasattr(field, "pre_save_callback"):
            self.meta.pre_save_fields.add(name)
        if hasattr(field, "post_delete_callback"):
            self.meta.post_delete_fields.add(name)
        if isinstance(field, BaseForeignKeyField):
            self.meta.foreign_key_fields.add(name)
        if isinstance(field, RelationshipField):
            self.meta.relationship_fields.add(name)
        if isinstance(field, BaseRefForeignKey):
            self.meta.ref_foreign_key_fields.add(name)

    def discard_field_from_meta(self, name: str) -> None:
        if self.meta._field_stats_are_initialized:
            for field_attr in _field_sets_to_clear:
                getattr(self.meta, field_attr).discard(name)

    def __getitem__(self, name: str) -> BaseFieldType:
        return cast(BaseFieldType, self.data[name])

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: str) -> bool:
        return key in self.data

    def __setitem__(self, name: str, value: BaseFieldType) -> None:
        if name in self.data:
            self.discard_field_from_meta(name)
        self.data[name] = value
        self.add_field_to_meta(name, value)
        if self.meta.model is not None:
            self.meta.model.model_fields[name] = value  # type: ignore
        self.meta.invalidate(invalidate_stats=False)

    def __delitem__(self, name: str) -> None:
        if self.data.pop(name, None) is not None:
            self.discard_field_from_meta(name)
            if self.meta.model is not None:
                self.meta.model.model_fields.pop(name, None)  # type: ignore
            self.meta.invalidate(invalidate_stats=False)


class FieldToColumns(UserDict, dict[str, Sequence["sqlalchemy.Column"]]):
    def __init__(self, meta: MetaInfo):
        self.meta = meta
        super().__init__()

    def __getitem__(self, name: str) -> Sequence[sqlalchemy.Column]:
        if name in self.data:
            return cast(Sequence["sqlalchemy.Column"], self.data[name])
        field = self.meta.fields[name]
        result = self.data[name] = field.get_columns(name)
        return result

    def __setitem__(self, name: str, value: Any) -> None:
        raise Exception("Cannot set item here")

    def __iter__(self) -> Any:
        self.meta.columns_to_field.init()
        return super().__iter__()

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: str) -> bool:
        try:
            self[key]
            return True
        except KeyError:
            return False


class FieldToColumnNames(FieldToColumns, dict[str, frozenset[str]]):
    def __getitem__(self, name: str) -> frozenset[str]:
        if name in self.data:
            return cast(frozenset[str], self.data[name])
        column_names = frozenset(column.key for column in self.meta.field_to_columns[name])
        result = self.data[name] = column_names
        return result


class ColumnsToField(UserDict, dict[str, str]):
    def __init__(self, meta: MetaInfo):
        self.meta = meta
        self._init = False
        super().__init__()

    def init(self) -> None:
        if not self._init:
            self._init = True
            _columns_to_field: dict[str, str] = {}
            for field_name in self.meta.fields:
                # init structure
                column_names = self.meta.field_to_column_names[field_name]
                for column_name in column_names:
                    if column_name in _columns_to_field:
                        raise ValueError(
                            f"column collision: {column_name} between field {field_name} and {_columns_to_field[column_name]}"
                        )
                    _columns_to_field[column_name] = field_name
            self.data.update(_columns_to_field)

    def __getitem__(self, name: str) -> str:
        self.init()
        return cast(str, super().__getitem__(name))

    def __setitem__(self, name: str, value: Any) -> None:
        raise Exception("Cannot set item here")

    def __contains__(self, name: str) -> bool:
        self.init()
        return super().__contains__(name)

    def __iter__(self) -> Any:
        self.init()
        return super().__iter__()


_trigger_attributes_fields_MetaInfo = {
    "field_to_columns",
    "field_to_column_names",
    "columns_to_field",
}

_trigger_attributes_field_stats_MetaInfo = {
    "foreign_key_fields",
    "special_getter_fields",
    "input_modifying_fields",
    "post_save_fields",
    "post_delete_fields",
    "excluded_fields",
    "secret_fields",
    "relationship_fields",
    "ref_foreign_key_fields",
}

_field_sets_to_clear: set[str] = _trigger_attributes_field_stats_MetaInfo


class MetaInfo:
    __slots__ = (
        "abstract",
        "inherit",
        "fields",
        "registry",
        "no_copy",
        "tablename",
        "unique_together",
        "indexes",
        "constraints",
        "model",
        "managers",
        "multi_related",
        "signals",
        "input_modifying_fields",
        "pre_save_fields",
        "post_save_fields",
        "post_delete_fields",
        "foreign_key_fields",
        "field_to_columns",
        "field_to_column_names",
        "columns_to_field",
        "special_getter_fields",
        "excluded_fields",
        "secret_fields",
        "relationship_fields",
        "ref_foreign_key_fields",
        "_needs_special_serialization",
        "_fields_are_initialized",
        "_field_stats_are_initialized",
    )
    _include_dump = (
        *filter(
            lambda x: x
            not in {
                "field_to_columns",
                "field_to_column_names",
                "columns_to_field",
                "_fields_are_initialized",
                "_field_stats_are_initialized",
            },
            __slots__,
        ),
        "pk",
    )

    fields: Fields
    field_to_columns: FieldToColumns
    field_to_column_names: FieldToColumnNames
    columns_to_field: ColumnsToField

    unique_together: list[Union[str, tuple, UniqueConstraint]]
    indexes: list[Index]
    constraints: list[sqlalchemy.Constraint]

    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        self._fields_are_initialized = False
        self._field_stats_are_initialized = False
        self.model: Optional[type[BaseModelType]] = None
        #  Difference between meta extraction and kwargs: meta attributes are copied
        self.abstract: bool = getattr(meta, "abstract", False)
        self.no_copy: bool = getattr(meta, "no_copy", False)
        # for embedding
        self.inherit: bool = getattr(meta, "inherit", True)
        self.registry: Union[Registry, Literal[False], None] = getattr(meta, "registry", None)
        self.tablename: Optional[str] = getattr(meta, "tablename", None)
        for attr in ["unique_together", "indexes", "constraints"]:
            attr_val: Any = getattr(meta, attr, [])
            if not isinstance(attr_val, (list, tuple)):
                raise ImproperlyConfigured(
                    f"{attr} must be a tuple or list. Got {type(attr_val).__name__} instead."
                )

            setattr(self, attr, list(attr_val))

        self.signals = signals_module.Broadcaster(getattr(meta, "signals", None) or {})
        self.signals.set_lifecycle_signals_from(signals_module, overwrite=False)
        self.fields = {**getattr(meta, "fields", _empty_dict)}  # type: ignore
        self.managers: dict[str, BaseManager] = {**getattr(meta, "managers", _empty_dict)}
        self.multi_related: set[tuple[str, str]] = {*getattr(meta, "multi_related", _empty_set)}
        self.load_dict(kwargs)

    @property
    def pk(self) -> Optional[PKField]:
        return cast(Optional[PKField], self.fields.get("pk"))

    @property
    def needs_special_serialization(self) -> bool:
        if getattr(self, "_needs_special_serialization", None) is None:
            _needs_special_serialization: bool = any(
                not self.fields[field_name].exclude for field_name in self.special_getter_fields
            )
            if not _needs_special_serialization:
                names = _seen_table_names.get()
                token = None
                if names is None:
                    names = set()
                    token = _seen_table_names.set(names)
                try:
                    for field_name in self.foreign_key_fields:
                        field = cast(BaseForeignKeyField, self.fields[field_name])
                        if field.target.table.key in names:
                            continue
                        else:
                            names.add(field.target.table.key)
                        if field.target.meta.needs_special_serialization:
                            _needs_special_serialization = True
                            break
                finally:
                    if token is not None:
                        _seen_table_names.reset(token)

            self._needs_special_serialization = _needs_special_serialization

        return self._needs_special_serialization

    @property
    def fields_mapping(self) -> dict[str, BaseFieldType]:
        warnings.warn(
            "'fields_mapping' has been deprecated, use 'fields' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.fields

    @property
    def is_multi(self) -> bool:
        warnings.warn(
            "`is_multi` is deprecated. Use bool(meta.multi_related) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return bool(self.multi_related)

    @property
    def parents(self) -> list[Any]:
        warnings.warn(
            "`parents` is deprecated and will be removed without replacement.",
            DeprecationWarning,
            stacklevel=2,
        )
        return [parent for parent in self.model.__bases__ if isinstance(parent, BaseModelMeta)]

    def model_dump(self) -> dict[Any, Any]:
        return {k: getattr(self, k, None) for k in self._include_dump}

    def load_dict(self, values: dict[str, Any]) -> None:
        """
        Loads the metadata from a dictionary.
        You may want to overload it to create hooks to ensure types.
        """
        for key, value in values.items():
            # we want triggering invalidate in case it is fields
            setattr(self, key, value)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "fields":
            value = Fields(self, value)
        super().__setattr__(name, value)
        if name == "fields":
            self.invalidate()

    def __getattribute__(self, name: str) -> Any:
        # lazy execute
        if name in _trigger_attributes_fields_MetaInfo and not self._fields_are_initialized:
            self.init_fields_mapping()
        if (
            name in _trigger_attributes_field_stats_MetaInfo
            and not self._field_stats_are_initialized
        ):
            self.init_field_stats()
        return super().__getattribute__(name)

    def init_fields_mapping(self) -> None:
        # when accessing the secret_fields in model_dump, this is triggered
        self.field_to_columns = FieldToColumns(self)
        self.field_to_column_names = FieldToColumnNames(self)
        self.columns_to_field = ColumnsToField(self)
        if self.model is not None:
            self.model.model_rebuild(force=True)
        self._fields_are_initialized = True

    def init_field_stats(self) -> None:
        self.special_getter_fields: set[str] = set()
        self.excluded_fields: set[str] = set()
        self.secret_fields: set[str] = set()
        self.input_modifying_fields: set[str] = set()
        self.post_save_fields: set[str] = set()
        self.pre_save_fields: set[str] = set()
        self.post_delete_fields: set[str] = set()
        self.foreign_key_fields: set[str] = set()
        self.relationship_fields: set[str] = set()
        self.ref_foreign_key_fields: set[str] = set()
        self._field_stats_are_initialized = True
        for key, field in self.fields.items():
            self.fields.add_field_to_meta(key, field)

    def invalidate(
        self,
        clear_class_attrs: bool = True,
        invalidate_fields: bool = True,
        invalidate_stats: bool = True,
    ) -> None:
        if invalidate_fields and self._fields_are_initialized:
            # prevent cycles and mem-leaks
            for attr in (
                "field_to_columns",
                "field_to_column_names",
                "columns_to_field",
            ):
                with contextlib.suppress(AttributeError):
                    delattr(self, attr)
            self._fields_are_initialized = False
        if invalidate_stats:
            self._field_stats_are_initialized = False
        if invalidate_fields or invalidate_stats:
            with contextlib.suppress(AttributeError):
                delattr(self, "_needs_special_serialization")
        if self.model is None:
            return
        if clear_class_attrs:
            for attr in ("_table", "_pknames", "_pkcolumns", "__proxy_model__"):
                with contextlib.suppress(AttributeError):
                    delattr(self.model, attr)
            # needs an extra invalidation
            self.model._db_schemas = {}

    def full_init(self, init_column_mappers: bool = True, init_class_attrs: bool = True) -> None:
        if not self._fields_are_initialized:
            self.init_fields_mapping()
        if not self._field_stats_are_initialized:
            self.init_field_stats()
        if init_column_mappers:
            self.columns_to_field.init()
        if init_class_attrs:
            for attr in ("table", "pknames", "pkcolumns", "proxy_model"):
                getattr(self.model, attr)

    def get_columns_for_name(self, name: str) -> Sequence[sqlalchemy.Column]:
        if name in self.field_to_columns:
            return self.field_to_columns[name]
        elif self.model and name in self.model.table.columns:
            return (self.model.table.columns[name],)
        else:
            return cast(Sequence["sqlalchemy.Column"], _empty_set)


def get_model_registry(
    bases: tuple[type, ...], meta_class: Optional[Union[object, MetaInfo]] = None
) -> Union[Registry, None, Literal[False]]:
    """
    When a registry is missing from the Meta class, it should look up for the bases
    and obtain the first found registry.
    """
    if meta_class is not None:
        direct_registry: Union[Registry, None, Literal[False]] = getattr(
            meta_class, "registry", None
        )
        if direct_registry is not None:
            return direct_registry

    for base in bases:
        meta: MetaInfo = getattr(base, "meta", None)
        # now check meta
        if meta is None:
            continue
        found_registry: Union[Registry, None, Literal[False]] = getattr(meta, "registry", None)

        if found_registry is not None:
            return found_registry
    return None


def _handle_annotations(base: type, base_annotations: dict[str, Any]) -> None:
    for parent in base.__mro__[1:]:
        _handle_annotations(parent, base_annotations)
    if hasattr(base, "__init_annotations__") and base.__init_annotations__:
        base_annotations.update(base.__init_annotations__)
    elif hasattr(base, "__annotations__") and base.__annotations__:
        # python 3.9 has no get_annotations
        base_annotations.update(base.__annotations__)


def handle_annotations(
    bases: tuple[type, ...], base_annotations: dict[str, Any], attrs: Any
) -> dict[str, Any]:
    """
    Handles and copies some of the annotations for
    initialisation.
    """
    for base in bases:
        _handle_annotations(base, base_annotations)

    annotations: dict[str, Any] = (
        copy.copy(attrs["__init_annotations__"])
        if "__init_annotations__" in attrs
        else copy.copy(attrs["__annotations__"])
    )
    annotations.update(base_annotations)
    return annotations


_occluded_sentinel = object()


def _extract_fields_and_managers(base: type, attrs: dict[str, Any]) -> None:
    from edgy.core.db.fields.composite_field import CompositeField

    meta: Union[MetaInfo, None] = getattr(base, "meta", None)
    if not meta:
        # Mixins and other classes
        # Note: from mixins BaseFields and BaseManagers are imported despite inherit=False until a model in the
        # hierarchy uses them
        # Here is _occluded_sentinel not overwritten
        for key, value in inspect.getmembers(base):
            if key not in attrs:
                if isinstance(value, BaseFieldType):
                    attrs[key] = value
                elif isinstance(value, BaseManager):
                    attrs[key] = value.__class__()
                elif isinstance(value, BaseModelMeta):
                    attrs[key] = CompositeField(
                        inner_fields=value,
                        prefix_embedded=f"{key}_",
                        inherit=value.meta.inherit,
                        name=key,
                        owner=value,
                    )
            elif attrs[key] is _occluded_sentinel:
                # when occluded only include if inherit is True
                if isinstance(value, BaseFieldType) and value.inherit:
                    attrs[key] = value
                elif isinstance(value, BaseManager) and value.inherit:
                    attrs[key] = value.__class__()
                elif isinstance(value, BaseModelMeta) and value.meta.inherit:
                    attrs[key] = CompositeField(
                        inner_fields=value,
                        prefix_embedded=f"{key}_",
                        inherit=value.meta.inherit,
                        name=key,
                        owner=value,
                    )

    else:
        # abstract classes
        for key, value in meta.fields.items():
            if key not in attrs:
                # when abstract or inherit passthrough
                if meta.abstract or value.inherit:
                    attrs[key] = value
                    assert value.owner is not None
                else:
                    attrs[key] = _occluded_sentinel
            elif attrs[key] is _occluded_sentinel and value.inherit:
                # when occluded only include if inherit is True
                attrs[key] = value
                assert value.owner is not None
        for key, value in meta.managers.items():
            if key not in attrs:
                # when abstract or inherit passthrough
                if meta.abstract or value.inherit:
                    attrs[key] = value
                else:
                    attrs[key] = _occluded_sentinel
            elif attrs[key] is _occluded_sentinel and value.inherit:
                # when occluded only include if inherit is True
                attrs[key] = value

    # from strongest to weakest
    for parent in base.__mro__[1:]:
        _extract_fields_and_managers(parent, attrs)


def extract_fields_and_managers(
    bases: Sequence[type], attrs: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """
    Search for fields and managers and return them.

    Managers are copied.

    Note: managers and fields with inherit=False are still extracted from mixins as long there is no intermediate model
    """

    from edgy.core.db.fields.composite_field import CompositeField

    attrs = {} if attrs is None else {**attrs}
    # order is important
    for key in list(attrs.keys()):
        value = attrs[key]
        if isinstance(value, BaseModelMeta):
            value = attrs[key]
            attrs[key] = CompositeField(
                inner_fields=value,
                prefix_embedded=f"{key}_",
                inherit=value.meta.inherit,
                owner=value,
            )
    for base in bases:
        _extract_fields_and_managers(base, attrs)
    # now remove sentinels
    for key in list(attrs.keys()):
        value = attrs[key]
        if value is _occluded_sentinel:
            attrs.pop(key)
    return attrs


class BaseModelMeta(ModelMetaclass, ABCMeta):
    __slots__ = ()

    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        attrs: dict[str, Any],
        meta_info_class: type[MetaInfo] = MetaInfo,
        skip_registry: Union[bool, Literal["allow_search"]] = False,
        on_conflict: Literal["error", "replace", "keep"] = "error",
        **kwargs: Any,
    ) -> Any:
        fields: dict[str, BaseFieldType] = {}
        managers: dict[str, BaseManager] = {}
        meta_class: object = attrs.get("Meta", type("Meta", (), {}))
        base_annotations: dict[str, Any] = {}
        has_explicit_primary_key = False
        is_abstract: bool = getattr(meta_class, "abstract", False)
        has_parents = any(isinstance(parent, BaseModelMeta) for parent in bases)

        # Extract the custom Edgy Fields in a pydantic format.
        attrs, model_fields = extract_field_annotations_and_defaults(attrs)
        # ensure they are clean
        attrs.pop("_pkcolumns", None)
        attrs.pop("_pknames", None)
        attrs.pop("_table", None)
        database: Union[Literal["keep"], None, Database, bool] = attrs.pop("database", "keep")

        # Extract fields and managers and include them in attrs
        attrs = extract_fields_and_managers(bases, attrs)

        for key, value in attrs.items():
            if isinstance(value, BaseFieldType):
                if key == "pk" and not isinstance(value, PKField):
                    raise ImproperlyConfigured(
                        f"Cannot add a field named pk to model {name}. Protected name."
                    )
                # make sure we have a fresh copy where we can set the owner and overwrite methods
                value = copy.copy(value)
                if value.factory is not None:
                    value.factory.repack(value)
                if value.primary_key:
                    has_explicit_primary_key = True
                # set as soon as possible the field_name
                value.name = key

                # add fields and non BaseRefForeignKeyField to fields
                # The BaseRefForeignKeyField is actually not a normal SQL Foreignkey
                # It is an Edgy specific operation that creates a reference to a ForeignKey
                # That is why is not stored as a normal FK but as a reference but
                # stored also as a field to be able later or to access anywhere in the model
                # and use the value for the creation of the records via RefForeignKey.
                # saving a reference foreign key.
                # We split the keys (store them) in different places to be able to easily maintain and
                #  what is what.
                fields[key] = value
                model_fields[key] = value
            elif isinstance(value, BaseManager):
                value = copy.copy(value)
                value.name = key
                managers[key] = value

        if not is_abstract:
            # the order is important because it reflects the inheritance order
            # from the strongest to the weakest
            fieldnames_to_check = deque(fields.keys())
            while fieldnames_to_check:
                # pop the weakest next field
                field_name = fieldnames_to_check.pop()
                field = fields[field_name]
                embedded_fields = field.get_embedded_fields(field_name, fields)
                if embedded_fields:
                    for sub_field_name, sub_field in embedded_fields.items():
                        if sub_field_name == "pk":
                            raise ValueError("sub field uses reserved name pk")

                        if sub_field_name in fields and fields[sub_field_name].owner is None:
                            raise ValueError(f"sub field name collision: {sub_field_name}")
                        # set as soon as possible the field_name
                        sub_field.name = sub_field_name
                        if sub_field.primary_key:
                            has_explicit_primary_key = True
                        # insert as stronger element
                        fieldnames_to_check.appendleft(sub_field_name)
                        fields[sub_field_name] = sub_field
                        model_fields[sub_field_name] = sub_field
            # Handle with multiple primary keys and auto generated field if no primary key is provided
            if not is_abstract and has_parents and not has_explicit_primary_key:
                if "id" not in fields:
                    if attrs.get("__reflected__", False):
                        raise ImproperlyConfigured(
                            f"Cannot create model {name}. No primary key found and reflected."
                        )
                    else:
                        model_fields["id"] = fields["id"] = edgy_fields.BigIntegerField(  # type: ignore
                            primary_key=True,
                            autoincrement=True,
                            inherit=False,
                            no_copy=True,
                            name="id",
                        )
                if not isinstance(fields["id"], BaseFieldType) or not fields["id"].primary_key:
                    raise ImproperlyConfigured(
                        f"Cannot create model {name} without explicit primary key if field 'id' is already present."
                    )

        for field_name, field_value in fields.items():
            attrs.pop(field_name, None)
            # clear cached target, target is property
            if isinstance(field_value, BaseForeignKey):
                del field_value.target

        for manager_name in managers:
            attrs.pop(manager_name, None)
        attrs["meta"] = meta = meta_info_class(
            meta_class,
            fields=fields,
            managers=managers,
        )
        del fields
        if is_abstract or not meta.fields:
            meta.abstract = True

        del is_abstract

        if not meta.abstract:
            model_fields["pk"] = meta.fields["pk"] = PKField(
                exclude=True, name="pk", inherit=False, no_copy=True
            )

        # Handle annotations
        annotations: dict[str, Any] = handle_annotations(bases, base_annotations, attrs)

        for k, _ in meta.managers.items():
            if annotations:
                if k not in annotations:
                    raise ImproperlyConfigured(
                        f"Managers must be type annotated and '{k}' is not annotated. Managers must be annotated with ClassVar."
                    )
                # evaluate annotation which can be a string reference.
                # because we really import ClassVar to check against it is safe to assume a ClassVar is available.
                if isinstance(annotations[k], str):
                    annotations[k] = eval(annotations[k])
                if get_origin(annotations[k]) is not ClassVar:
                    raise ImproperlyConfigured("Managers must be ClassVar type annotated.")

        # Ensure the initialization is only performed for subclasses of EdgyBaseModel
        attrs["__init_annotations__"] = annotations

        new_class = cast(type["Model"], super().__new__(cls, name, bases, attrs, **kwargs))
        meta.model = new_class
        # Ensure initialization is only performed for subclasses of edgy.Model
        # (excluding the edgy.Model class itself).
        if not has_parents:
            return new_class
        new_class._db_schemas = {}

        model_fields_on_class = getattr(new_class, "__pydantic_fields__", None)
        if model_fields_on_class is None:
            model_fields_on_class = new_class.model_fields
        for key in list(model_fields_on_class.keys()):
            model_field_on_class = model_fields_on_class[key]
            if isinstance(model_field_on_class, BaseFieldType):
                del model_fields_on_class[key]
        model_fields_on_class.update(model_fields)

        # Set the owner of the field, must be done as early as possible
        # don't use meta.fields to not trigger the lazy evaluation
        for value in meta.fields.values():
            value.owner = new_class
        # set the model_class of managers
        for value in meta.managers.values():
            value.owner = new_class

        # inherited unique_together
        for base in new_class.__bases__:
            if hasattr(base, "meta") and base.meta.unique_together:
                meta.unique_together.extend(base.meta.unique_together)

        if meta.unique_together:
            unique_together = meta.unique_together
            for value in unique_together:
                if not isinstance(value, (str, tuple, UniqueConstraint)):
                    raise ValueError(
                        "The values inside the unique_together must be a string, a tuple of strings or an instance of UniqueConstraint."
                    )

        # inherited indexes
        for base in new_class.__bases__:
            if hasattr(base, "meta") and base.meta.indexes:
                meta.indexes.extend(base.meta.indexes)

        # Handle indexes
        if meta.indexes:
            indexes = meta.indexes
            for value in indexes:
                if not isinstance(value, Index):
                    raise ValueError("Meta.indexes must be a list of Index types.")

        # inherited constraints
        for base in new_class.__bases__:
            if hasattr(base, "meta") and base.meta.constraints:
                meta.constraints.extend(base.meta.constraints)

        # Handle constraints
        if meta.constraints:
            constraints = meta.constraints
            for value in constraints:
                if not isinstance(value, sqlalchemy.Constraint):
                    raise ValueError(
                        "Meta.constraints must be a list of sqlalchemy.Constraint type."
                    )

        # Making sure the tablename is always set if the value is not provided
        if getattr(meta, "tablename", None) is None:
            tablename = f"{name.lower()}s"
            meta.tablename = tablename
        meta.model = new_class

        # Now find a registry and add it to the meta.
        if meta.registry is None and skip_registry is not True:
            registry: Union[Registry, None, Literal[False]] = get_model_registry(bases, meta_class)
            meta.registry = registry or None
        # don't add automatically to registry. Useful for subclasses which modify the registry itself.
        # `skip_registry="allow_search"` is trueish so it works.
        if not meta.registry or skip_registry:
            new_class.model_rebuild(force=True)
            return new_class

        new_class.add_to_registry(meta.registry, database=database, on_conflict=on_conflict)
        return new_class

    def get_db_schema(cls) -> Union[str, None]:
        """
        Returns a db_schema from registry if any is passed.
        """
        if hasattr(cls, "meta") and getattr(cls.meta, "registry", None):
            return cls.meta.registry.db_schema  # type: ignore
        return None

    def get_db_shema(cls) -> Union[str, None]:
        warnings.warn(
            "'get_db_shema' has been deprecated, use 'get_db_schema' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return cls.get_db_schema()

    def _build_table(cls, metadata: Optional[sqlalchemy.MetaData] = None) -> None:
        try:
            cls._table = cls.build(cls.get_db_schema(), metadata=metadata)
        except AttributeError as exc:
            raise TableBuildError(exc) from exc

    @property
    def table(cls) -> sqlalchemy.Table:
        """
        Making sure the tables on inheritance state, creates the new
        one properly.

        Making sure the following scenarios are met:

        1. If there is a context_db_schema, it will return for those, which means, the `using`
        if being utilised.
        2. If a db_schema in the `registry` is passed, then it will use that as a default.
        3. If none is passed, defaults to the shared schema of the database connected.
        """
        if cls.__is_proxy_model__:
            return cls.__parent__.table  # type: ignore
        if not cls.meta.registry:
            # we cannot set the table without a registry
            # raising is required
            raise AttributeError("No registry.")
        table = getattr(cls, "_table", None)
        # assert table.name.lower() == cls.meta.tablename, f"{table.name.lower()} != {cls.meta.tablename}"
        # fix assigned table
        if table is None or table.name.lower() != cls.meta.tablename:
            cls._build_table()

        return cast("sqlalchemy.Table", cls._table)

    def __getattr__(cls, name: str) -> Any:
        """
        For controlling inheritance we cannot have manager descriptors, so fake them
        """
        manager = cls.meta.managers.get(name)
        if manager is not None:
            return manager
        return super().__getattr__(name)

    @property
    def pkcolumns(cls) -> Sequence[str]:
        if cls.__dict__.get("_pkcolumns", None) is None:
            cls._pkcolumns = build_pkcolumns(cls)
        return cast(Sequence[str], cls._pkcolumns)

    @property
    def pknames(cls) -> Sequence[str]:
        if cls.__dict__.get("_pknames", None) is None:
            cls._pknames = build_pknames(cls)
        return cast(Sequence[str], cls._pknames)

    @property
    def signals(cls) -> signals_module.Broadcaster:
        """
        Returns the signals of a class
        """
        warnings.warn(
            "'signals' has been deprecated, use 'meta.signals' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        meta: MetaInfo = cls.meta
        return meta.signals

    def transaction(cls, *, force_rollback: bool = False, **kwargs: Any) -> Transaction:
        """Return database transaction for the assigned database"""
        return cast(
            "Transaction", cls.database.transaction(force_rollback=force_rollback, **kwargs)
        )

    def table_schema(
        cls,
        schema: Union[str, None] = None,
        *,
        metadata: Optional[sqlalchemy.MetaData] = None,
        update_cache: bool = False,
    ) -> sqlalchemy.Table:
        """
        Retrieve table for schema (nearly the same as build with scheme argument).
        Cache per class via a primitive LRU cache.
        """
        if cls.__is_proxy_model__:
            return cls.__parent__.table_schema(  # type: ignore
                schema, metadata=metadata, update_cache=update_cache
            )
        if schema is None or (cls.get_db_schema() or "") == schema:
            # sqlalchemy uses "" for empty schema
            table = getattr(cls, "_table", None)
            if update_cache or table is None or table.name.lower() != cls.meta.tablename:
                cls._build_table(metadata=metadata)
            return cls.table
        # remove cache element so the key is reordered
        schema_obj = cls._db_schemas.pop(schema, None)
        if schema_obj is None or update_cache:
            schema_obj = cls.build(schema=schema, metadata=metadata)
        # set element to last
        cls._db_schemas[schema] = schema_obj
        # remove oldest element, when bigger 100
        while len(cls._db_schemas) > 100:
            cls._db_schemas.pop(next(iter(cls._db_schemas)), None)

        return cast("sqlalchemy.Table", schema_obj)

    @property
    def proxy_model(cls: type[Model]) -> type[Model]:
        """
        Returns the proxy_model from the Model when called using the cache.
        """
        if cls.__is_proxy_model__:
            return cls
        if getattr(cls, "__proxy_model__", None) is None:
            proxy_model = cls.generate_proxy_model()
            proxy_model.__parent__ = cls
            proxy_model.model_rebuild(force=True)
            cls.__proxy_model__ = proxy_model
        return cls.__proxy_model__

    @property
    def columns(cls) -> sqlalchemy.sql.ColumnCollection:
        return cast("sqlalchemy.sql.ColumnCollection", cls.table.columns)

    @property
    def fields(cls) -> dict[str, BaseFieldType]:
        warnings.warn(
            "'fields' has been deprecated, use 'meta.fields' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        meta: MetaInfo = cls.meta
        return meta.fields
