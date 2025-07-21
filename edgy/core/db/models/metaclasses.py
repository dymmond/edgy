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
from edgy.core.db.fields.many_to_many import BaseManyToManyForeignKeyField
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

    meta: MetaInfo

    def __init__(self, meta: MetaInfo, data: dict[str, BaseFieldType] | None = None):
        """
        Initializes the Fields object.

        Args:
            meta: The MetaInfo object associated with these fields.
            data: An optional dictionary of initial field data.
        """
        self.meta = meta
        super().__init__(data)

    def add_field_to_meta(self, name: str, field: BaseFieldType) -> None:
        """
        Adds a field to the MetaInfo's statistical sets if field stats are initialized.

        Args:
            name: The name of the field.
            field: The field object to add.
        """
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

            # This is particularly useful for M2M distinguish
            # Mostly for the admin manipulation
            if isinstance(field, BaseManyToManyForeignKeyField):
                self.meta.many_to_many_fields.add(name)
        if isinstance(field, BaseRefForeignKey):
            self.meta.ref_foreign_key_fields.add(name)

    def discard_field_from_meta(self, name: str) -> None:
        """
        Discards a field from the MetaInfo's statistical sets if field stats are initialized.

        Args:
            name: The name of the field to discard.
        """
        if self.meta._field_stats_are_initialized:
            for field_attr in _field_sets_to_clear:
                getattr(self.meta, field_attr).discard(name)

    def __getitem__(self, name: str) -> BaseFieldType:
        """
        Retrieves a field by name.

        Args:
            name: The name of the field.

        Returns:
            The field object.
        """
        return cast(BaseFieldType, self.data[name])

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieves a field by key, with an optional default value.

        Args:
            key: The key of the field.
            default: The default value to return if the key is not found.

        Returns:
            The field object or the default value.
        """
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: str) -> bool:
        """
        Checks if a key exists in the fields.

        Args:
            key: The key to check.

        Returns:
            True if the key exists, False otherwise.
        """
        return key in self.data

    def __setitem__(self, name: str, value: BaseFieldType) -> None:
        """
        Sets a field with the given name and value. Invalidates meta-information.

        Args:
            name: The name of the field.
            value: The field object.
        """
        if name in self.data:
            self.discard_field_from_meta(name)
        self.data[name] = value
        self.add_field_to_meta(name, value)
        if self.meta.model is not None:
            self.meta.model.model_fields[name] = value
        self.meta.invalidate(invalidate_stats=False)

    def __delitem__(self, name: str) -> None:
        """
        Deletes a field by name. Invalidates meta-information.

        Args:
            name: The name of the field to delete.
        """
        if self.data.pop(name, None) is not None:
            self.discard_field_from_meta(name)
            if self.meta.model is not None:
                self.meta.model.model_fields.pop(name, None)
            self.meta.invalidate(invalidate_stats=False)


class FieldToColumns(UserDict, dict[str, Sequence[sqlalchemy.Column]]):
    """
    Manages the mapping from field names to their corresponding SQLAlchemy columns.
    """

    meta: MetaInfo

    def __init__(self, meta: MetaInfo):
        """
        Initializes the FieldToColumns object.

        Args:
            meta: The MetaInfo object associated with these columns.
        """
        self.meta = meta
        super().__init__()

    def __getitem__(self, name: str) -> Sequence[sqlalchemy.Column]:
        """
        Retrieves the SQLAlchemy columns for a given field name.

        Args:
            name: The name of the field.

        Returns:
            A sequence of SQLAlchemy Column objects.
        """
        if name in self.data:
            return cast(Sequence[sqlalchemy.Column], self.data[name])
        field = self.meta.fields[name]
        result = self.data[name] = field.get_columns(name)
        return result

    def __setitem__(self, name: str, value: Any) -> None:
        """
        This method is not supported for FieldToColumns.

        Raises:
            Exception: Always raises an exception as setting items directly is not allowed.
        """
        raise Exception("Cannot set item here")

    def __iter__(self) -> Any:
        """
        Initializes the columns_to_field mapping and returns an iterator over the keys.
        """
        self.meta.columns_to_field.init()
        return super().__iter__()

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieves the SQLAlchemy columns for a given key, with an optional default value.

        Args:
            key: The key of the field.
            default: The default value to return if the key is not found.

        Returns:
            A sequence of SQLAlchemy Column objects or the default value.
        """
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: str) -> bool:
        """
        Checks if a key exists in the mapping.

        Args:
            key: The key to check.

        Returns:
            True if the key exists, False otherwise.
        """
        try:
            self[key]
            return True
        except KeyError:
            return False


class FieldToColumnNames(FieldToColumns, dict[str, frozenset[str]]):
    """
    Manages the mapping from field names to their corresponding SQLAlchemy column names.
    """

    def __getitem__(self, name: str) -> frozenset[str]:
        """
        Retrieves the SQLAlchemy column names for a given field name.

        Args:
            name: The name of the field.

        Returns:
            A frozenset of column names.
        """
        if name in self.data:
            return cast(frozenset[str], self.data[name])
        column_names = frozenset(column.key for column in self.meta.field_to_columns[name])
        result = self.data[name] = column_names
        return result


class ColumnsToField(UserDict, dict[str, str]):
    """
    Manages the mapping from SQLAlchemy column names to their corresponding field names.
    """

    meta: MetaInfo
    _init: bool

    def __init__(self, meta: MetaInfo):
        """
        Initializes the ColumnsToField object.

        Args:
            meta: The MetaInfo object associated with these mappings.
        """
        self.meta = meta
        self._init = False
        super().__init__()

    def init(self) -> None:
        """
        Initializes the mapping from column names to field names.
        This method ensures that the mapping is built only once.

        Raises:
            ValueError: If a column name collision is detected.
        """
        if not self._init:
            self._init = True
            _columns_to_field: dict[str, str] = {}
            for field_name in self.meta.fields:
                # init structure
                column_names = self.meta.field_to_column_names[field_name]
                for column_name in column_names:
                    if column_name in _columns_to_field:
                        raise ValueError(
                            f"column collision: {column_name} between field {field_name} "
                            f"and {_columns_to_field[column_name]}"
                        )
                    _columns_to_field[column_name] = field_name
            self.data.update(_columns_to_field)

    def __getitem__(self, name: str) -> str:
        """
        Retrieves the field name for a given column name. Ensures initialization.

        Args:
            name: The name of the column.

        Returns:
            The name of the field.
        """
        self.init()
        return cast(str, super().__getitem__(name))

    def __setitem__(self, name: str, value: Any) -> None:
        """
        This method is not supported for ColumnsToField.

        Raises:
            Exception: Always raises an exception as setting items directly is not allowed.
        """
        raise Exception("Cannot set item here")

    def __contains__(self, name: str) -> bool:
        """
        Checks if a column name exists in the mapping. Ensures initialization.

        Args:
            name: The column name to check.

        Returns:
            True if the column name exists, False otherwise.
        """
        self.init()
        return super().__contains__(name)

    def __iter__(self) -> Any:
        """
        Ensures initialization and returns an iterator over the keys.
        """
        self.init()
        return super().__iter__()


_trigger_attributes_fields_MetaInfo: set[str] = {
    "field_to_columns",
    "field_to_column_names",
    "columns_to_field",
}

_trigger_attributes_field_stats_MetaInfo: set[str] = {
    "foreign_key_fields",
    "special_getter_fields",
    "input_modifying_fields",
    "post_save_fields",
    "post_delete_fields",
    "excluded_fields",
    "secret_fields",
    "relationship_fields",
    "many_to_many_fields",
    "ref_foreign_key_fields",
}

_field_sets_to_clear: set[str] = _trigger_attributes_field_stats_MetaInfo


class MetaInfo:
    """
    Manages the metadata information for a model, including fields, managers,
    table details, and various field-related statistics.
    """

    __slots__ = (
        "abstract",
        "inherit",
        "fields",
        "registry",
        "no_copy",
        "in_admin",
        "no_admin_create",
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
        "many_to_many_fields",
        "ref_foreign_key_fields",
        "_needs_special_serialization",
        "_fields_are_initialized",
        "_field_stats_are_initialized",
    )
    _include_dump: tuple[str, ...] = (
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
    unique_together: list[str | tuple | UniqueConstraint]
    indexes: list[Index]
    constraints: list[sqlalchemy.Constraint]
    model: type[BaseModelType] | None
    managers: dict[str, BaseManager]
    signals: signals_module.Broadcaster
    multi_related: set[tuple[str, str]]
    abstract: bool
    no_copy: bool
    inherit: bool
    in_admin: bool | None
    no_admin_create: bool | None
    registry: Registry | Literal[False] | None
    tablename: str | None
    _fields_are_initialized: bool
    _field_stats_are_initialized: bool
    _needs_special_serialization: bool | None
    input_modifying_fields: set[str]
    pre_save_fields: set[str]
    post_save_fields: set[str]
    post_delete_fields: set[str]
    foreign_key_fields: set[str]
    relationship_fields: set[str]
    many_to_many_fields: set[str]
    ref_foreign_key_fields: set[str]
    special_getter_fields: set[str]
    excluded_fields: set[str]
    secret_fields: set[str]

    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        """
        Initializes the MetaInfo object, processing attributes from a given meta class
        and keyword arguments.

        Args:
            meta: An optional meta class from which to extract attributes.
            kwargs: Additional keyword arguments to load into the MetaInfo.

        Raises:
            ImproperlyConfigured: If 'unique_together', 'indexes', or 'constraints'
                                  are not lists or tuples.
        """
        self._fields_are_initialized = False
        self._field_stats_are_initialized = False
        self.model = None
        # Difference between meta extraction and kwargs: meta attributes are copied
        self.abstract = getattr(meta, "abstract", False)
        self.no_copy = getattr(meta, "no_copy", False)
        # for embedding
        self.inherit = getattr(meta, "inherit", True)
        self.in_admin = getattr(meta, "in_admin", None)
        self.no_admin_create = getattr(meta, "no_admin_create", None)
        self.registry = getattr(meta, "registry", None)
        self.tablename = getattr(meta, "tablename", None)
        for attr in ["unique_together", "indexes", "constraints"]:
            attr_val: Any = getattr(meta, attr, [])
            if not isinstance(attr_val, list | tuple):
                raise ImproperlyConfigured(
                    f"{attr} must be a tuple or list. Got {type(attr_val).__name__} instead."
                )

            setattr(self, attr, list(attr_val))

        self.signals = signals_module.Broadcaster(getattr(meta, "signals", None) or {})
        self.signals.set_lifecycle_signals_from(signals_module, overwrite=False)
        self.fields = {**getattr(meta, "fields", _empty_dict)}  # type: ignore
        self.managers = {**getattr(meta, "managers", _empty_dict)}
        self.multi_related = {*getattr(meta, "multi_related", _empty_set)}
        self.load_dict(kwargs)

    @property
    def pk(self) -> PKField | None:
        """
        Returns the primary key field of the model.
        """
        return cast(PKField | None, self.fields.get("pk"))

    @property
    def needs_special_serialization(self) -> bool:
        """
        Determines if the model requires special serialization due to specific field types,
        such as special getter fields or foreign key fields with nested special serialization.
        """
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
        """
        Returns a mapping of field names to field objects.

        Deprecated: Use `fields` instead.
        """
        warnings.warn(
            "'fields_mapping' has been deprecated, use 'fields' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.fields

    @property
    def is_multi(self) -> bool:
        """
        Checks if the model has multiple relationships.

        Deprecated: Use `bool(meta.multi_related)` instead.
        """
        warnings.warn(
            "`is_multi` is deprecated. Use bool(meta.multi_related) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return bool(self.multi_related)

    @property
    def parents(self) -> list[Any]:
        """
        Returns a list of parent models.

        Deprecated: Will be removed without replacement.
        """
        warnings.warn(
            "`parents` is deprecated and will be removed without replacement.",
            DeprecationWarning,
            stacklevel=2,
        )
        return [parent for parent in self.model.__bases__ if isinstance(parent, BaseModelMeta)]

    def model_dump(self) -> dict[Any, Any]:
        """
        Dumps the relevant metadata information into a dictionary.
        """
        return {k: getattr(self, k, None) for k in self._include_dump}

    def load_dict(self, values: dict[str, Any]) -> None:
        """
        Loads the metadata from a dictionary.
        This method can be overloaded to create hooks to ensure types.

        Args:
            values: The dictionary containing metadata values.
        """
        for key, value in values.items():
            # we want triggering invalidate in case it is fields
            setattr(self, key, value)

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Sets an attribute on the MetaInfo object. Special handling for 'fields'
        to ensure proper initialization and invalidation.

        Args:
            name: The name of the attribute to set.
            value: The value to set.
        """
        if name == "fields":
            value = Fields(self, value)
        super().__setattr__(name, value)
        if name == "fields":
            self.invalidate()

    def __getattribute__(self, name: str) -> Any:
        """
        Custom attribute access to lazily initialize field mappings and field statistics
        when certain attributes are accessed.
        """
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
        """
        Initializes the mappings between fields and columns, and column names.
        This method is called lazily when relevant attributes are accessed.
        """
        self.field_to_columns = FieldToColumns(self)
        self.field_to_column_names = FieldToColumnNames(self)
        self.columns_to_field = ColumnsToField(self)
        if self.model is not None:
            self.model.model_rebuild(force=True)
        self._fields_are_initialized = True

    def init_field_stats(self) -> None:
        """
        Initializes various sets for tracking field statistics, such as foreign keys,
        special getters, excluded fields, etc. This method is called lazily.
        """
        self.special_getter_fields = set()
        self.excluded_fields = set()
        self.secret_fields = set()
        self.input_modifying_fields = set()
        self.post_save_fields = set()
        self.pre_save_fields = set()
        self.post_delete_fields = set()
        self.foreign_key_fields = set()
        self.relationship_fields = set()
        self.many_to_many_fields = set()
        self.ref_foreign_key_fields = set()
        self._field_stats_are_initialized = True
        for key, field in self.fields.items():
            self.fields.add_field_to_meta(key, field)

    def invalidate(
        self,
        clear_class_attrs: bool = True,
        invalidate_fields: bool = True,
        invalidate_stats: bool = True,
    ) -> None:
        """
        Invalidates cached metadata information, optionally clearing class attributes,
        field mappings, and field statistics.

        Args:
            clear_class_attrs: If True, clears cached class attributes like _table, _pknames.
            invalidate_fields: If True, invalidates field mapping caches.
            invalidate_stats: If True, invalidates field statistics caches.
        """
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
        """
        Performs a full initialization of the MetaInfo, including field mappings,
        field statistics, column mappers, and class attributes.

        Args:
            init_column_mappers: If True, initializes the column to field mapping.
            init_class_attrs: If True, initializes class attributes like table, pknames.
        """
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
        """
        Retrieves the SQLAlchemy columns associated with a given field name.

        Args:
            name: The name of the field.

        Returns:
            A sequence of SQLAlchemy Column objects.
        """
        if name in self.field_to_columns:
            return self.field_to_columns[name]
        elif self.model and name in self.model.table.columns:
            return (self.model.table.columns[name],)
        else:
            return cast(Sequence[sqlalchemy.Column], _empty_set)


def get_model_meta_attr(
    attr: str, bases: tuple[type, ...], meta_class: object | MetaInfo | None = None
) -> Any | None:
    """
    Retrieves a specific attribute from the Meta class, looking up the inheritance
    chain if the attribute is missing or None in the direct Meta class.

    Args:
        attr: The name of the attribute to retrieve.
        bases: A tuple of base classes to check for the attribute.
        meta_class: An optional Meta class instance or object to check first.

    Returns:
        The value of the attribute if found, otherwise None.
    """
    if meta_class is not None:
        direct_attr: Any = getattr(meta_class, attr, None)
        if direct_attr is not None:
            return direct_attr

    for base in bases:
        meta: MetaInfo = getattr(base, "meta", None)
        # now check meta
        if meta is None:
            continue
        found_attr: Any = getattr(meta, attr, None)

        if found_attr is not None:
            return found_attr
    return None


def get_model_registry(
    bases: tuple[type, ...], meta_class: object | MetaInfo | None = None
) -> Registry | None | Literal[False]:
    """
    Retrieves the Registry from the Meta class, looking up the inheritance
    chain if the registry is missing in the direct Meta class.

    Args:
        bases: A tuple of base classes to check for the registry.
        meta_class: An optional Meta class instance or object to check first.

    Returns:
        The Registry instance if found, otherwise None or False.
    """
    return cast(
        "Registry | None | Literal[False]",
        get_model_meta_attr("registry", bases=bases, meta_class=meta_class),
    )


def _handle_annotations(base: type, base_annotations: dict[str, Any]) -> None:
    """
    Recursively handles and updates annotations from base classes into `base_annotations`.

    Args:
        base: The current base class being processed.
        base_annotations: The dictionary to accumulate annotations.
    """
    for parent in base.__mro__[1:]:
        _handle_annotations(parent, base_annotations)
    if hasattr(base, "__init_annotations__") and base.__init_annotations__:
        base_annotations.update(base.__init_annotations__)
    elif hasattr(base, "__annotations__") and base.__annotations__:
        base_annotations.update(inspect.get_annotations(base, eval_str=False))


def handle_annotations(
    bases: tuple[type, ...], base_annotations: dict[str, Any], attrs: Any
) -> dict[str, Any]:
    """
    Handles and copies annotations for initialisation, merging annotations from
    base classes and the current class attributes.

    Args:
        bases: A tuple of base classes.
        base_annotations: A dictionary to store annotations from base classes.
        attrs: The attributes of the current class being created.

    Returns:
        A dictionary containing the combined annotations.
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
    """
    Recursively extracts fields and managers from base classes and updates the
    `attrs` dictionary. Handles inheritance and occlusion.

    Args:
        base: The current base class being processed.
        attrs: The dictionary of attributes for the current class being built.
    """
    from edgy.core.db.fields.composite_field import CompositeField

    meta: MetaInfo | None = getattr(base, "meta", None)
    if not meta:
        # Mixins and other classes
        # Note: from mixins BaseFields and BaseManagers are imported despite inherit=False until
        # a model in the hierarchy uses them. Here is _occluded_sentinel not overwritten.
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
    bases: Sequence[type], attrs: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Searches for fields and managers in base classes and returns them.
    Managers are copied.

    Note: managers and fields with inherit=False are still extracted from mixins
    as long as there is no intermediate model.

    Args:
        bases: A sequence of base classes to extract from.
        attrs: An optional dictionary of attributes to start with.

    Returns:
        A dictionary containing extracted fields and managers.
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
    """
    Metaclass for Edgy models, handling the creation and registration of models,
    processing fields, managers, and metadata.
    """

    __slots__ = ()

    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        attrs: dict[str, Any],
        meta_info_class: type[MetaInfo] = MetaInfo,
        skip_registry: bool | Literal["allow_search"] = False,
        on_conflict: Literal["error", "replace", "keep"] = "error",
        **kwargs: Any,
    ) -> type:
        """
        Creates a new Edgy model class. This method processes model fields, managers,
        metadata, and handles inheritance.

        Args:
            name: The name of the new class.
            bases: A tuple of base classes.
            attrs: A dictionary of attributes for the new class.
            meta_info_class: The class to use for storing meta information.
            skip_registry: If True, skips adding the model to the registry.
                           If "allow_search", it allows searching for a registry
                           but won't automatically add it if found.
            on_conflict: Strategy to handle conflicts when adding to the registry
                         ("error", "replace", "keep").
            kwargs: Additional keyword arguments passed to the Pydantic ModelMetaclass.

        Returns:
            The newly created model class.

        Raises:
            ImproperlyConfigured: If a field named 'pk' is added but is not a PKField,
                                  or if managers are not type annotated with ClassVar,
                                  or if a model is reflected without a primary key.
            ValueError: If a sub-field uses the reserved name 'pk' or if a sub-field
                        name collision occurs, or if `unique_together` values are invalid,
                        or if `indexes` are not `Index` types, or `constraints` are not
                        `sqlalchemy.Constraint` types.
        """
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
        database: Literal["keep"] | None | Database | bool = attrs.pop("database", "keep")

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
                # We split the keys (store them) in different places to be able to easily maintain
                # and what is what.
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
            # Handle with multiple primary keys and auto generated field if no primary key
            # is provided
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
                        f"Cannot create model {name} without explicit primary key if field 'id' "
                        "is already present."
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
                        f"Managers must be type annotated and '{k}' is not annotated. Managers "
                        "must be annotated with ClassVar."
                    )
                # evaluate annotation which can be a string reference.
                # because we really import ClassVar to check against it is safe to assume a
                # ClassVar is available.
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

        # extract attributes
        for base in new_class.__bases__:
            if hasattr(base, "meta"):
                # FIXME: deduplicate and normalize (unique together) elements of shared ancestors
                # here we can use sets
                # we might want to undeprecate parents and use them
                if base.meta.unique_together:
                    meta.unique_together.extend(base.meta.unique_together)

                if base.meta.indexes:
                    meta.indexes.extend(base.meta.indexes)

                if base.meta.constraints:
                    meta.constraints.extend(base.meta.constraints)
        meta.in_admin = get_model_meta_attr("in_admin", bases, meta)
        meta.no_admin_create = get_model_meta_attr("no_admin_create", bases, meta)

        if meta.unique_together:
            unique_together = meta.unique_together
            for value in unique_together:
                if not isinstance(value, str | tuple | UniqueConstraint):
                    raise ValueError(
                        "The values inside the unique_together must be a string, a tuple of strings"
                        " or an instance of UniqueConstraint."
                    )
        # Handle indexes
        if meta.indexes:
            indexes = meta.indexes
            for value in indexes:
                if not isinstance(value, Index):
                    raise ValueError("Meta.indexes must be a list of Index types.")

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
            registry: Registry | None | Literal[False] = get_model_registry(bases, meta_class)
            meta.registry = registry or None
        # don't add automatically to registry. Useful for subclasses which modify the registry itself.
        # `skip_registry="allow_search"` is trueish so it works.
        if not meta.registry or skip_registry:
            new_class.model_rebuild(force=True)
            return new_class

        new_class.add_to_registry(meta.registry, database=database, on_conflict=on_conflict)
        return new_class

    def get_db_schema(cls) -> str | None:
        """
        Returns the database schema from the model's registry, if available.
        """
        if hasattr(cls, "meta") and getattr(cls.meta, "registry", None):
            return cls.meta.registry.db_schema  # type: ignore
        return None

    def get_db_shema(cls) -> str | None:
        """
        Returns the database schema from the model's registry, if available.

        Deprecated: Use `get_db_schema` instead.
        """
        warnings.warn(
            "'get_db_shema' has been deprecated, use 'get_db_schema' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return cls.get_db_schema()

    def _build_table(cls, metadata: sqlalchemy.MetaData | None = None) -> None:
        """
        Internal method to build the SQLAlchemy table for the model.

        Args:
            metadata: An optional SQLAlchemy MetaData object to associate with the table.

        Raises:
            TableBuildError: If an AttributeError occurs during table building.
        """
        try:
            cls._table = cls.build(cls.get_db_schema(), metadata=metadata)
        except AttributeError as exc:
            raise TableBuildError(exc) from exc

    @property
    def table(cls) -> sqlalchemy.Table:
        """
        Returns the SQLAlchemy Table object associated with the model.
        Handles table creation based on inheritance and registry schema.

        Making sure the following scenarios are met:

        1. If there is a context_db_schema, it will return for those, which means, the `using`
        is being utilised.
        2. If a db_schema in the `registry` is passed, then it will use that as a default.
        3. If none is passed, defaults to the shared schema of the database connected.

        Raises:
            AttributeError: If no registry is found for the model, preventing table creation.
        """
        if cls.__is_proxy_model__:
            return cls.__parent__.table  # type: ignore
        if not cls.meta.registry:
            # we cannot set the table without a registry
            # raising is required
            raise AttributeError("No registry.")
        table = getattr(cls, "_table", None)
        # assert table.name.lower() == cls.meta.tablename, f"{table.name.lower()} !=
        # {cls.meta.tablename}"
        # fix assigned table
        if table is None or table.name.lower() != cls.meta.tablename:
            cls._build_table()

        return cast("sqlalchemy.Table", cls._table)

    def __getattr__(cls, name: str) -> Any:
        """
        Custom attribute access to provide manager descriptors, allowing managers
        to be accessed directly as attributes of the model.
        """
        manager = cls.meta.managers.get(name)
        if manager is not None:
            return manager
        return super().__getattr__(name)

    @property
    def pkcolumns(cls) -> Sequence[str]:
        """
        Returns a sequence of primary key column names for the model.
        """
        if cls.__dict__.get("_pkcolumns", None) is None:
            cls._pkcolumns = build_pkcolumns(cls)
        return cast(Sequence[str], cls._pkcolumns)

    @property
    def pknames(cls) -> Sequence[str]:
        """
        Returns a sequence of primary key field names for the model.
        """
        if cls.__dict__.get("_pknames", None) is None:
            cls._pknames = build_pknames(cls)
        return cast(Sequence[str], cls._pknames)

    @property
    def signals(cls) -> signals_module.Broadcaster:
        """
        Returns the signals broadcaster associated with the model.

        Deprecated: Use `meta.signals` instead.
        """
        warnings.warn(
            "'signals' has been deprecated, use 'meta.signals' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        meta: MetaInfo = cls.meta
        return meta.signals

    def transaction(cls, *, force_rollback: bool = False, **kwargs: Any) -> Transaction:
        """
        Returns a database transaction for the assigned database.

        Args:
            force_rollback: If True, forces the transaction to rollback.
            kwargs: Additional keyword arguments for the transaction.

        Returns:
            A Transaction object.
        """
        return cast(
            "Transaction", cls.database.transaction(force_rollback=force_rollback, **kwargs)
        )

    def table_schema(
        cls,
        schema: str | None = None,
        *,
        metadata: sqlalchemy.MetaData | None = None,
        update_cache: bool = False,
    ) -> sqlalchemy.Table:
        """
        Retrieves or builds the SQLAlchemy table for a specific schema.
        Uses a primitive LRU cache for schema-specific tables.

        Args:
            schema: The database schema name. If None, uses the default schema.
            metadata: An optional SQLAlchemy MetaData object.
            update_cache: If True, forces an update of the cache for the given schema.

        Returns:
            The SQLAlchemy Table object for the specified schema.
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
        Returns the proxy model for the current model, creating it if it doesn't exist.
        The proxy model is cached on the class.
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
        """
        Returns the SQLAlchemy ColumnCollection for the model's table.
        """
        return cast("sqlalchemy.sql.ColumnCollection", cls.table.columns)

    @property
    def fields(cls) -> dict[str, BaseFieldType]:
        """
        Returns a dictionary of field names to BaseFieldType objects for the model.

        Deprecated: Use `meta.fields` instead.
        """
        warnings.warn(
            "'fields' has been deprecated, use 'meta.fields' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        meta: MetaInfo = cls.meta
        return meta.fields
