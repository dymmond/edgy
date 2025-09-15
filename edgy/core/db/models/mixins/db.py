from __future__ import annotations

import contextlib
import copy
import inspect
import sys
import warnings
from collections.abc import Awaitable, Callable, Collection, Sequence
from functools import partial
from itertools import chain
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

import sqlalchemy
from pydantic import BaseModel

from edgy.core.db.constants import CASCADE
from edgy.core.db.context_vars import (
    CURRENT_FIELD_CONTEXT,
    CURRENT_INSTANCE,
    CURRENT_MODEL_INSTANCE,
    EXPLICIT_SPECIFIED_VALUES,
    MODEL_GETATTR_BEHAVIOR,
    NO_GLOBAL_FIELD_CONSTRAINTS,
    get_schema,
)
from edgy.core.db.datastructures import Index, UniqueConstraint
from edgy.core.db.fields.base import BaseForeignKey
from edgy.core.db.fields.many_to_many import BaseManyToManyForeignKeyField
from edgy.core.db.models.metaclasses import MetaInfo
from edgy.core.db.models.types import BaseModelType
from edgy.core.db.models.utils import build_pkcolumns
from edgy.core.db.relationships.related_field import RelatedField
from edgy.core.utils.db import check_db_connection, hash_names
from edgy.core.utils.models import create_edgy_model
from edgy.exceptions import ForeignKeyBadConfigured, ModelCollisionError, ObjectNotFound
from edgy.types import Undefined

if sys.version_info >= (3, 11):  # pragma: no cover
    from typing import Self
else:  # pragma: no cover
    from typing_extensions import Self

if TYPE_CHECKING:
    from databasez.core.transaction import Transaction

    from edgy.core.connection.database import Database
    from edgy.core.connection.registry import Registry
    from edgy.core.db.fields.types import FIELD_CONTEXT_TYPE, BaseFieldType
    from edgy.core.db.models.model import Model
    from edgy.core.db.querysets.base import QuerySet


_empty = cast(set[str], frozenset())


class _EmptyClass: ...


_removed_copy_keys = {
    *BaseModel.__dict__.keys(),
    "_db_loaded",
    "_db_deleted",
    "_pkcolumns",
    "_table",
    "_db_schemas",
    "__proxy_model__",
    "meta",
    "transaction",
}
_removed_copy_keys.difference_update(
    {*_EmptyClass.__dict__.keys(), "__annotations__", "__module__"}
)


def _check_replace_related_field(
    replace_related_field: bool
    | type[BaseModelType]
    | tuple[type[BaseModelType], ...]
    | list[type[BaseModelType]],
    model: type[BaseModelType],
) -> bool:
    """
    Checks if a related field should be replaced based on the provided configuration.

    Args:
        replace_related_field: A boolean, a model type, or a sequence of model types
                               indicating whether the related field should be replaced.
        model: The model type to check against the replacement configuration.

    Returns:
        True if the related field should be replaced, False otherwise.
    """
    if isinstance(replace_related_field, bool):
        return replace_related_field
    if not isinstance(replace_related_field, tuple | list):
        replace_related_field = (replace_related_field,)
    return any(refmodel is model for refmodel in replace_related_field)


def _set_related_field(
    target: type[BaseModelType],
    *,
    foreign_key_name: str,
    related_name: str,
    source: type[BaseModelType],
    replace_related_field: bool
    | type[BaseModelType]
    | tuple[type[BaseModelType], ...]
    | list[type[BaseModelType]],
) -> None:
    """
    Sets the related field on the target model.

    This function creates a `RelatedField` instance and assigns it to the target
    model's metadata. It also handles cascade deletion settings based on the
    foreign key's configuration.

    Args:
        target: The model type to which the related field will be added.
        foreign_key_name: The name of the foreign key field in the source model.
        related_name: The name of the related field to be set on the target model.
        source: The source model type that declares the foreign key.
        replace_related_field: A boolean, a model type, or a sequence of model types
                               indicating whether an existing related field should be
                               replaced if a conflict occurs.

    Raises:
        ForeignKeyBadConfigured: If multiple related names with the same value are
                                 found pointing to the same target, and replacement
                                 is not explicitly allowed for the conflicting related
                                 from model.
    """
    if replace_related_field is not True and related_name in target.meta.fields:
        # is already correctly set, required for migrate of model_apps with registry set
        related_field = target.meta.fields[related_name]
        if (
            related_field.related_from is source
            and related_field.foreign_key_name == foreign_key_name
        ):
            return
        # required for copying
        if related_field.foreign_key_name != foreign_key_name or _check_replace_related_field(
            replace_related_field, related_field.related_from
        ):
            raise ForeignKeyBadConfigured(
                f"Multiple related_name with the same value '{related_name}' found to "
                "the same target. Related names must be different."
            )
    # now we have enough data
    fk = source.meta.fields[foreign_key_name]
    if fk.force_cascade_deletion_relation or (
        fk.on_delete == CASCADE
        and (source.meta.registry is not target.meta.registry or fk.no_constraint)
    ):
        fk.relation_has_post_delete_callback = True
        fk.force_cascade_deletion_relation = True

    related_field = RelatedField(
        foreign_key_name=foreign_key_name,
        name=related_name,
        owner=target,
        related_from=source,
    )

    # Set the related name
    target.meta.fields[related_name] = related_field


def _set_related_name_for_foreign_keys(
    meta: MetaInfo,
    model_class: type[BaseModelType],
    replace_related_field: bool
    | type[BaseModelType]
    | tuple[type[BaseModelType], ...]
    | list[type[BaseModelType]] = False,
) -> None:
    """
    Sets the related name for the foreign keys within a model's metadata.

    When a `related_name` is generated or explicitly provided, this function
    creates a `RelatedField` that links the model declaring the foreign key
    to the target model of the foreign key. This allows for reverse relationships.

    Args:
        meta: The `MetaInfo` object of the model class, containing its fields.
        model_class: The model class for which to set related names.
        replace_related_field: A boolean, a model type, or a sequence of model types
                               indicating whether an existing related field should be
                               replaced if a conflict occurs during registration.
    """
    if not meta.foreign_key_fields:
        return

    for name in meta.foreign_key_fields:
        foreign_key = meta.fields[name]
        related_name = getattr(foreign_key, "related_name", None)
        if related_name is False:
            # skip related_field
            continue

        if not related_name:
            if foreign_key.unique:
                related_name = f"{model_class.__name__.lower()}"
            else:
                related_name = f"{model_class.__name__.lower()}s_set"

        foreign_key.related_name = related_name
        foreign_key.reverse_name = related_name

        related_field_fn = partial(
            _set_related_field,
            source=model_class,
            foreign_key_name=name,
            related_name=related_name,
            replace_related_field=replace_related_field,
        )
        registry: Registry = foreign_key.target_registry
        with contextlib.suppress(Exception):
            registry = cast("Registry", foreign_key.target.registry)
        registry.register_callback(foreign_key.to, related_field_fn, one_time=True)


def _fixup_rel_annotation(target: type[BaseModelType], field: BaseFieldType) -> None:
    """
    Adjusts the type annotation for a related field based on its type (M2M or nullable).

    Args:
        target: The target model type of the relationship.
        field: The field whose annotation needs to be fixed.
    """
    if field.is_m2m:
        field.field_type = field.annotation = list[target]  # type: ignore
    elif field.null:
        field.field_type = field.annotation = None | target
    else:
        field.field_type = field.annotation = target


def _fixup_rel_annotations(meta: MetaInfo) -> None:
    """
    Fixes up the type annotations for all foreign key and many-to-many fields
    within a model's metadata.

    This ensures that the type hints correctly reflect the related model types,
    which is crucial for validation and static analysis.

    Args:
        meta: The `MetaInfo` object of the model, containing its fields.
    """
    for name in chain(meta.foreign_key_fields, meta.many_to_many_fields):
        field = meta.fields[name]
        registry: Registry = field.target_registry
        with contextlib.suppress(Exception):
            registry = cast("Registry", field.target.registry)
        registry.register_callback(
            field.to, partial(_fixup_rel_annotation, field=field), one_time=True
        )


class DatabaseMixin:
    """
    A mixin class providing database-related functionalities for models.

    This includes methods for interacting with the database such as saving,
    updating, deleting, and loading model instances, as well as managing
    database schemas and model registration.
    """

    _removed_copy_keys: ClassVar[set[str]] = _removed_copy_keys

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initializes the DatabaseMixin.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)
        self.transaction = self.not_set_transaction

    @classmethod
    def real_add_to_registry(
        cls: type[BaseModelType],
        *,
        registry: Registry,
        registry_type_name: str = "models",
        name: str = "",
        database: bool | Database | Literal["keep"] = "keep",
        replace_related_field: bool
        | type[BaseModelType]
        | tuple[type[BaseModelType], ...]
        | list[type[BaseModelType]] = False,
        on_conflict: Literal["keep", "replace", "error"] = "error",
    ) -> type[BaseModelType]:
        """
        Registers the model class with the provided registry.

        This method handles the core logic for adding a model to a registry,
        including managing database connections, resolving model name conflicts,
        and setting up relationships (foreign keys and many-to-many fields).

        Args:
            registry: The `Registry` instance to which the model will be added.
            registry_type_name: The name of the registry dictionary to use (e.g., "models").
            name: An optional name to assign to the model in the registry. If not
                  provided, the class's `__name__` will be used.
            database: Specifies how the database connection should be handled.
                      `True` means use the registry's database; `False` means no database;
                      `"keep"` means retain the current database if set, otherwise use
                      the registry's; a `Database` instance means use that specific database.
            replace_related_field: A boolean, a model type, or a sequence of model types
                                   indicating whether existing related fields should be
                                   replaced if conflicts arise during registration.
            on_conflict: Defines the behavior when a model with the same name is
                         already registered. Can be "keep" (return existing model),
                         "replace" (overwrite existing model), or "error" (raise
                         `ModelCollisionError`).

        Returns:
            The registered model class.

        Raises:
            ModelCollisionError: If a model with the same name is already registered
                                 and `on_conflict` is "error".
        """
        # when called if registry is not set
        cls.meta.registry = registry
        if database is True:
            cls.database = registry.database
        elif database is not False:
            if database == "keep":
                if getattr(cls, "database", None) is None:
                    cls.database = registry.database

            else:
                cls.database = database
        meta = cls.meta
        if name:
            cls.__name__ = name

        # Making sure it does not generate models if abstract or a proxy
        if not meta.abstract and not cls.__is_proxy_model__:
            if on_conflict == "replace":
                registry.delete_model(cls.__name__)
            else:
                with contextlib.suppress(LookupError):
                    original_model = registry.get_model(
                        cls.__name__,
                        include_content_type_attr=False,
                        exclude=("tenant_models",),
                    )
                    if on_conflict == "keep":
                        return original_model
                    else:
                        raise ModelCollisionError(
                            detail=(
                                f'A model with the same name is already registered: "{cls.__name__}".\n'
                                "If this is not a bug, define the behaviour by "
                                'setting "on_conflict" to either "keep" or "replace".'
                            )
                        )
            if registry_type_name:
                registry_dict = getattr(registry, registry_type_name)
                registry_dict[cls.__name__] = cls
                # after registrating the own model
                for value in list(meta.fields.values()):
                    if isinstance(value, BaseManyToManyForeignKeyField):
                        m2m_registry: Registry = value.target_registry
                        with contextlib.suppress(Exception):
                            m2m_registry = cast("Registry", value.target.registry)

                        def create_through_model(x: Any, field: BaseFieldType = value) -> None:
                            # we capture with field = ... the variable
                            field.create_through_model(replace_related_field=replace_related_field)

                        m2m_registry.register_callback(
                            value.to, create_through_model, one_time=True
                        )
                # Sets the foreign key fields
                if meta.foreign_key_fields:
                    _set_related_name_for_foreign_keys(
                        meta, cls, replace_related_field=replace_related_field
                    )
                # fixup annotations required for validation
                if meta.foreign_key_fields or meta.many_to_many_fields:
                    _fixup_rel_annotations(meta)
                registry.execute_model_callbacks(cls)

        # finalize
        cls.model_rebuild(force=True)
        return cls

    @classmethod
    def add_to_registry(
        cls,
        registry: Registry,
        name: str = "",
        database: bool | Database | Literal["keep"] = "keep",
        *,
        replace_related_field: bool
        | type[BaseModelType]
        | tuple[type[BaseModelType], ...]
        | list[type[BaseModelType]] = False,
        on_conflict: Literal["keep", "replace", "error"] = "error",
    ) -> type[BaseModelType]:
        """
        A public wrapper for `real_add_to_registry`.

        This method provides a convenient interface for registering a model class
        with a given registry, forwarding all parameters to `real_add_to_registry`.

        Args:
            registry: The `Registry` instance to which the model will be added.
            name: An optional name to assign to the model in the registry.
            database: Specifies how the database connection should be handled.
            replace_related_field: Indicates whether existing related fields should
                                   be replaced.
            on_conflict: Defines the behavior when a model with the same name is
                         already registered.

        Returns:
            The registered model class.
        """
        return cls.real_add_to_registry(
            registry=registry,
            name=name,
            database=database,
            replace_related_field=replace_related_field,
            on_conflict=on_conflict,
        )

    def get_active_instance_schema(
        self, check_schema: bool = True, check_tenant: bool = True
    ) -> str | None:
        """
        Retrieves the active schema for the current model instance.

        This method first checks if a schema is explicitly set for the instance.
        If not, it defers to `get_active_class_schema` to determine the schema
        based on class-level configurations and global context.

        Args:
            check_schema: If True, checks for a global schema in the context.
            check_tenant: If True, considers tenant-specific schemas.

        Returns:
            The active schema as a string, or None if no schema is found.
        """
        if self._edgy_namespace["__using_schema__"] is not Undefined:
            return cast(str | None, self._edgy_namespace["__using_schema__"])
        return type(self).get_active_class_schema(
            check_schema=check_schema, check_tenant=check_tenant
        )

    @classmethod
    def get_active_class_schema(cls, check_schema: bool = True, check_tenant: bool = True) -> str:
        """
        Retrieves the active schema for the model class.

        This method determines the schema based on the class's `__using_schema__`
        attribute, global schema context, and the model's configured database schema.

        Args:
            check_schema: If True, checks for a global schema in the context.
            check_tenant: If True, considers tenant-specific schemas when checking
                          the global schema.

        Returns:
            The active schema as a string.
        """
        if cls.__using_schema__ is not Undefined:
            return cast(str | None, cls.__using_schema__)
        if check_schema:
            schema = get_schema(check_tenant=check_tenant)
            if schema is not None:
                return schema
        db_schema: str | None = cls.get_db_schema()
        # sometime "" is ok, sometimes not, sqlalchemy logic
        return db_schema or None

    @classmethod
    def copy_edgy_model(
        cls: type[Model],
        registry: Registry | None = None,
        name: str = "",
        unlink_same_registry: bool = True,
        on_conflict: Literal["keep", "replace", "error"] = "error",
        **kwargs: Any,
    ) -> type[Self]:
        """
        Copies the model class and optionally registers it with another registry.

        This method creates a deep copy of the model, including its fields and
        managers. It can also reconfigure foreign key and many-to-many relationships
        to point to models within a new registry or disable backreferences.

        Args:
            registry: An optional `Registry` instance to which the copied model
                      should be added. If `None`, the model is not added to any registry.
            name: An optional new name for the copied model. If not provided,
                  the original model's name is used.
            unlink_same_registry: If True, and the `registry` is different from the
                                  original model's registry, foreign key targets
                                  that point to models within the original registry
                                  will be unreferenced, forcing them to be resolved
                                  within the new registry.
            on_conflict: Defines the behavior if a model with the same name already
                         exists in the target registry (if `registry` is provided).
            **kwargs: Additional keyword arguments to pass to `create_edgy_model`.

        Returns:
            The newly created and copied model class.
        """
        # removes private pydantic stuff, except the prefixed ones
        attrs = {
            key: val for key, val in cls.__dict__.items() if key not in cls._removed_copy_keys
        }
        # managers and fields are gone, we have to readd them with the correct data
        attrs.update(
            (
                (field_name, field)
                for field_name, field in cls.meta.fields.items()
                if not field.no_copy
            )
        )
        attrs.update(cls.meta.managers)
        _copy = create_edgy_model(
            __name__=name or cls.__name__,
            __module__=cls.__module__,
            __definitions__=attrs,
            __metadata__=cls.meta,
            __bases__=cls.__bases__,
            __type_kwargs__={**kwargs, "skip_registry": True},
        )
        # should also allow masking database with None
        if hasattr(cls, "database"):
            _copy.database = cls.database
        replaceable_models: list[type[BaseModelType]] = [cls]
        if cls.meta.registry:
            for field_name in list(_copy.meta.fields):
                src_field = cls.meta.fields.get(field_name)
                if not isinstance(src_field, BaseForeignKey):
                    continue
                # we use the target of source
                replaceable_models.append(src_field.target)

                if src_field.target_registry is cls.meta.registry:
                    # clear target_registry, for obvious registries
                    del _copy.meta.fields[field_name].target_registry
                if unlink_same_registry and src_field.target_registry is cls.meta.registry:
                    # we need to unreference so the target is retrieved from the new registry

                    _copy.meta.fields[field_name].target = src_field.target.__name__
                else:
                    # otherwise we need to disable backrefs
                    _copy.meta.fields[field_name].related_name = False

                if isinstance(src_field, BaseManyToManyForeignKeyField):
                    _copy.meta.fields[field_name].through = src_field.through_original
                    # clear through registry, we need a copy in the new registry
                    del _copy.meta.fields[field_name].through_registry
                    if (
                        isinstance(_copy.meta.fields[field_name].through, type)
                        and issubclass(_copy.meta.fields[field_name].through, BaseModelType)
                        and not _copy.meta.fields[field_name].through.meta.abstract
                    ):
                        # unreference
                        _copy.meta.fields[field_name].through = through_model = _copy.meta.fields[
                            field_name
                        ].through.copy_edgy_model()
                        # we want to set the registry explicit
                        through_model.meta.registry = False
                        if src_field.from_foreign_key in through_model.meta.fields:
                            # explicit set
                            through_model.meta.fields[src_field.from_foreign_key].target = _copy
                            through_model.meta.fields[
                                src_field.from_foreign_key
                            ].related_name = cast(
                                BaseManyToManyForeignKeyField,
                                cast(type[BaseModelType], src_field.through).meta.fields[
                                    src_field.from_foreign_key
                                ],
                            ).related_name
        if registry is not None:
            # replace when old class otherwise old references can lead to issues
            _copy.add_to_registry(
                registry,
                replace_related_field=replaceable_models,
                on_conflict=on_conflict,
                database=(
                    "keep"
                    if cls.meta.registry is False or cls.database is not cls.meta.registry.database
                    else True
                ),
            )
        return cast("type[Self]", _copy)

    @property
    def table(self) -> sqlalchemy.Table:
        """
        Returns the SQLAlchemy table associated with the model instance.

        If the table is not already set on the instance, it will be built
        dynamically based on the active schema.

        Returns:
            The SQLAlchemy `Table` object.
        """
        if self._edgy_namespace.get("_table") is None:
            schema = self.get_active_instance_schema()
            return cast(
                "sqlalchemy.Table",
                type(self).table_schema(schema),
            )
        return cast("sqlalchemy.Table", self._edgy_namespace["_table"])

    @table.setter
    def table(self, value: sqlalchemy.Table | None) -> None:
        """
        Sets the SQLAlchemy table for the model instance.

        Clears cached primary key columns when the table is reset.

        Args:
            value: The SQLAlchemy `Table` object to set.
        """
        assert isinstance(value, sqlalchemy.Table), f"Cannot assign: {value!r} to table."
        self._edgy_namespace.pop("_pkcolumns", None)
        self._edgy_namespace["_table"] = value

    @table.deleter
    def table(self) -> None:
        """
        Deletes the SQLAlchemy table associated with the model instance.

        Also clears cached primary key columns.
        """
        self._edgy_namespace.pop("_pkcolumns", None)
        self._edgy_namespace.pop("_table", None)

    @property
    def pkcolumns(self) -> Sequence[str]:
        """
        Returns the names of the primary key columns for the model instance.

        If not already cached, it builds them based on the model's table.

        Returns:
            A sequence of strings representing the primary key column names.
        """
        if self._edgy_namespace.get("_pkcolumns") is None:
            if self._edgy_namespace.get("_table") is None:
                self._edgy_namespace["_pkcolumns"] = type(self).pkcolumns
            else:
                self._edgy_namespace["_pkcolumns"] = build_pkcolumns(self)
        return cast(Sequence[str], self._edgy_namespace["_pkcolumns"])

    @property
    def pknames(self) -> Sequence[str]:
        """
        Returns the logical names of the primary key fields for the model.

        Returns:
            A sequence of strings representing the primary key field names.
        """
        return cast(Sequence[str], type(self).pknames)

    def __setattr__(self, key: str, value: Any) -> None:
        """
        Custom `__setattr__` method to handle specific attribute assignments.

        If the `__using_schema__` attribute is set, it clears the cached
        `_table` to ensure the table is rebuilt with the new schema.

        Args:
            key: The name of the attribute to set.
            value: The value to assign to the attribute.
        """
        if key == "__using_schema__":
            self._edgy_namespace.pop("_table", None)
        super().__setattr__(key, value)

    def get_columns_for_name(self: Model, name: str) -> Sequence[sqlalchemy.Column]:
        """
        Retrieves the SQLAlchemy columns associated with a given field name.

        Args:
            name: The name of the field.

        Returns:
            A sequence of SQLAlchemy `Column` objects.
        """
        table = self.table
        meta = self.meta
        if name in meta.field_to_columns:
            return meta.field_to_columns[name]
        elif name in table.columns:
            return (table.columns[name],)
        else:
            return cast(Sequence[sqlalchemy.Column], _empty)

    def identifying_clauses(self, prefix: str = "") -> list[Any]:
        """
        Generates SQLAlchemy clauses for identifying the current model instance.

        These clauses are typically used in WHERE conditions for update and delete
        operations, based on the model's identifying database fields (usually primary keys).

        Args:
            prefix: An optional prefix to apply to column names in the clauses.
                    (Currently, this feature is not fully implemented and will
                    raise a `NotImplementedError` if used.)

        Returns:
            A list of SQLAlchemy clause elements.

        Raises:
            NotImplementedError: If a prefix is provided.
        """
        # works only if the class of the model is the main class of the queryset
        # TODO: implement prefix handling and return generic column without table attached
        if prefix:
            raise NotImplementedError()
        clauses: list[Any] = []
        for field_name in self.identifying_db_fields:
            field = self.meta.fields.get(field_name)
            if field is not None:
                for column_name, value in field.clean(
                    field_name, self.__dict__[field_name]
                ).items():
                    clauses.append(getattr(self.table.columns, column_name) == value)
            else:
                clauses.append(
                    getattr(self.table.columns, field_name) == self.__dict__[field_name]
                )
        return clauses

    async def _update(
        self: Model,
        is_partial: bool,
        kwargs: dict[str, Any],
        pre_fn: Callable[..., Awaitable[Any]],
        post_fn: Callable[..., Awaitable[Any]],
        instance: BaseModelType | QuerySet,
    ) -> int | None:
        """
        Internal method to perform an update operation on a model instance in the database.

        This method handles the extraction of column values, execution of pre-save hooks,
        database interaction for updating records, and post-save hook execution.

        Args:
            is_partial: A boolean indicating if this is a partial update.
            kwargs: A dictionary of key-value pairs representing the fields to update.
            pre_fn: An asynchronous callable to be executed before the update.
            post_fn: An asynchronous callable to be executed after the update.
            instance: The model instance or queryset initiating the update.

        Returns:
            The number of rows updated, or None if no update was performed.
        """
        real_class = self.get_real_class()
        column_values = self.extract_column_values(
            extracted_values=kwargs,
            is_partial=is_partial,
            is_update=True,
            phase="prepare_update",
            instance=self,
            model_instance=self,
            evaluate_values=True,
        )
        await pre_fn(
            real_class,
            model_instance=self,
            instance=instance,
            values=kwargs,
            column_values=column_values,
        )
        # empty updates shouldn't cause an error. E.g. only model references are updated
        clauses = self.identifying_clauses()
        row_count: int | None = None
        if column_values and clauses:
            check_db_connection(self.database, stacklevel=4)
            async with self.database as database, database.transaction():
                # can update column_values
                column_values.update(
                    await self.execute_pre_save_hooks(column_values, kwargs, is_update=True)
                )
                expression = self.table.update().values(**column_values).where(*clauses)
                row_count = cast(int, await database.execute(expression))

            # Update the model instance.
            new_kwargs = self.transform_input(column_values, phase="post_update", instance=self)
            self.__dict__.update(new_kwargs)

        # updates aren't required to change the db, they can also just affect the meta fields
        await self.execute_post_save_hooks(cast(Sequence[str], kwargs.keys()), is_update=True)

        if column_values or kwargs:
            # Ensure on access refresh the results is active
            self._db_deleted = False if row_count is None else row_count == 0
            self._db_loaded = False
        await post_fn(
            real_class,
            model_instance=self,
            instance=instance,
            values=kwargs,
            column_values=column_values,
        )
        return row_count

    async def update(self: Model, **kwargs: Any) -> Self:
        """
        Updates the current model instance in the database with the provided keyword arguments.

        This method triggers pre-update and post-update signals.

        Args:
            **kwargs: Keyword arguments representing the fields and their new values
                      to update.

        Returns:
            The updated model instance.
        """
        token = EXPLICIT_SPECIFIED_VALUES.set(set(kwargs.keys()))
        token2 = CURRENT_INSTANCE.set(self)
        try:
            # assume always partial
            await self._update(
                True,
                kwargs,
                pre_fn=partial(
                    self.meta.signals.pre_update.send_async, is_update=True, is_migration=False
                ),
                post_fn=partial(
                    self.meta.signals.post_update.send_async, is_update=True, is_migration=False
                ),
                instance=self,
            )
        finally:
            EXPLICIT_SPECIFIED_VALUES.reset(token)
            CURRENT_INSTANCE.reset(token2)
        return cast("Self", self)

    async def raw_delete(
        self: Model, *, skip_post_delete_hooks: bool, remove_referenced_call: bool | str
    ) -> int:
        """
        Performs the low-level delete operation from the database.

        This method handles pre-delete signals, cascades deletions (if configured),
        and post-delete cleanup.

        Args:
            skip_post_delete_hooks: If True, post-delete hooks will not be executed.
            remove_referenced_call: A boolean or string indicating if the deletion
                                    is triggered by a referenced call (e.g., cascade delete).
                                    If a string, it represents the field name that triggered it.

        Returns:
            The number of rows deleted.
        """
        if self._db_deleted:
            return 0
        instance = CURRENT_INSTANCE.get()
        real_class = self.get_real_class()
        # remove_referenced_call = called from a deleter of another field or model
        with_signals = self.__deletion_with_signals__ and (
            instance is not self or remove_referenced_call
        )
        if with_signals:
            await self.meta.signals.pre_delete.send_async(
                real_class, instance=instance, model_instance=self
            )
        ignore_fields: set[str] = set()
        if remove_referenced_call and isinstance(remove_referenced_call, str):
            ignore_fields.add(remove_referenced_call)
        # get values before deleting
        field_values: dict[str, Any] = {}
        if not skip_post_delete_hooks and self.meta.post_delete_fields.difference(ignore_fields):
            token = MODEL_GETATTR_BEHAVIOR.set("coro")
            try:
                for field_name in self.meta.post_delete_fields.difference(ignore_fields):
                    try:
                        field_value = getattr(self, field_name)
                    except AttributeError:
                        # already deleted
                        continue
                    if inspect.isawaitable(field_value):
                        try:
                            field_value = await field_value
                        except AttributeError:
                            # already deleted
                            continue
                    field_values[field_name] = field_value
            finally:
                MODEL_GETATTR_BEHAVIOR.reset(token)
        clauses = self.identifying_clauses()
        row_count = 0
        if clauses:
            expression = self.table.delete().where(*clauses)
            check_db_connection(self.database)
            async with self.database as database:
                row_count = cast(int, await database.execute(expression))
        # we cannot load anymore afterwards
        self._db_deleted = True
        # now cleanup with the saved values
        if field_values:
            token_instance = CURRENT_MODEL_INSTANCE.set(self)
            field_dict: FIELD_CONTEXT_TYPE = cast("FIELD_CONTEXT_TYPE", {})
            token_field_ctx = CURRENT_FIELD_CONTEXT.set(field_dict)
            try:
                for field_name, value in field_values.items():
                    field = self.meta.fields[field_name]
                    field_dict.clear()
                    field_dict["field"] = field
                    await field.post_delete_callback(value)
            finally:
                CURRENT_FIELD_CONTEXT.reset(token_field_ctx)
                CURRENT_MODEL_INSTANCE.reset(token_instance)
        if with_signals:
            await self.meta.signals.post_delete.send_async(
                real_class,
                instance=CURRENT_INSTANCE.get(),
                model_instance=self,
                row_count=row_count,
            )
        return row_count

    async def delete(self: Model, skip_post_delete_hooks: bool = False) -> None:
        """
        Deletes the current model instance from the database.

        This method triggers pre-delete and post-delete signals.

        Args:
            skip_post_delete_hooks: If True, post-delete hooks will not be executed.
        """
        real_class = self.get_real_class()
        await self.meta.signals.pre_delete.send_async(
            real_class, instance=self, model_instance=self
        )
        token = CURRENT_INSTANCE.set(self)
        try:
            row_count = await self.raw_delete(
                skip_post_delete_hooks=skip_post_delete_hooks,
                remove_referenced_call=False,
            )
        finally:
            CURRENT_INSTANCE.reset(token)
        await self.meta.signals.post_delete.send_async(
            real_class, instance=self, model_instance=self, row_count=row_count
        )

    async def load(self, only_needed: bool = False) -> None:
        """
        Loads the current model instance's data from the database.

        This method fetches the record corresponding to the instance's identifying
        clauses and updates the instance's attributes. If `only_needed` is True,
        it skips loading if the instance is already loaded or marked as deleted.

        Args:
            only_needed: If True, loads data only if the instance is not already
                         loaded or deleted.

        Raises:
            ObjectNotFound: If no row is found in the database corresponding to
                            the instance's identifying clauses.
        """
        if only_needed and self._db_loaded_or_deleted:
            return
        row = None
        clauses = self.identifying_clauses()
        if clauses:
            # Build the select expression.
            expression = self.table.select().where(*clauses)

            # Perform the fetch.
            check_db_connection(self.database)
            async with self.database as database:
                row = await database.fetch_one(expression)
        # check if is in system
        if row is None:
            self._db_deleted = True
            self._db_loaded = True
            raise ObjectNotFound("row does not exist anymore")
        # Update the instance.
        self.__dict__.update(self.transform_input(dict(row._mapping), phase="load", instance=self))
        self._db_deleted = False
        self._db_loaded = True

    async def check_exist_in_db(self, only_needed: bool = False) -> bool:
        """
        Checks if the current model instance exists in the database.

        Args:
            only_needed: If True, performs the check only if the instance's loaded
                         or deleted status is not conclusive.

        Returns:
            True if the instance exists in the database, False otherwise.
        """
        if only_needed:
            if self._db_deleted:
                return False
            if self._db_loaded:
                return True
        clauses = self.identifying_clauses()
        if not clauses:
            return False

        # Build the select expression.
        expression = self.table.select().where(*clauses).exists().select()

        # Perform the fetch.
        check_db_connection(self.database)
        async with self.database as database:
            result = cast(bool, await database.fetch_val(expression))
            self._db_deleted = not result
            return result

    async def _insert(
        self: Model,
        evaluate_values: bool,
        kwargs: dict[str, Any],
        pre_fn: Callable[..., Awaitable[Any]],
        post_fn: Callable[..., Awaitable[Any]],
        instance: BaseModelType | QuerySet,
    ) -> None:
        """
        Internal method to perform an insert operation for a model instance into the database.

        This method handles the extraction of column values, execution of pre-save hooks,
        database insertion, and post-save hook execution.

        Args:
            evaluate_values: A boolean indicating whether values should be evaluated
                             before insertion (e.g., for default values).
            kwargs: A dictionary of key-value pairs representing the fields to insert.
            pre_fn: An asynchronous callable to be executed before the insert.
            post_fn: An asynchronous callable to be executed after the insert.
            instance: The model instance or queryset initiating the insert.
        """
        real_class = self.get_real_class()
        column_values: dict[str, Any] = self.extract_column_values(
            extracted_values=kwargs,
            is_partial=False,
            is_update=False,
            phase="prepare_insert",
            instance=instance,
            model_instance=self,
            evaluate_values=evaluate_values,
        )
        await pre_fn(
            real_class,
            model_instance=self,
            instance=instance,
            column_values=column_values,
            values=kwargs,
        )
        check_db_connection(self.database, stacklevel=4)
        async with self.database as database, database.transaction():
            # can update column_values
            column_values.update(
                await self.execute_pre_save_hooks(column_values, kwargs, is_update=False)
            )
            expression = self.table.insert().values(**column_values)
            autoincrement_value = await database.execute(expression)
        # sqlalchemy supports only one autoincrement column
        if autoincrement_value:
            column = self.table.autoincrement_column
            if column is not None and hasattr(autoincrement_value, "_mapping"):
                autoincrement_value = autoincrement_value._mapping[column.key]
            # can be explicit set, which causes an invalid value returned
            if column is not None and column.key not in column_values:
                column_values[column.key] = autoincrement_value

        new_kwargs = self.transform_input(column_values, phase="post_insert", instance=self)
        self.__dict__.update(new_kwargs)

        if self.meta.post_save_fields:
            await self.execute_post_save_hooks(cast(Sequence[str], kwargs.keys()), is_update=False)
        # Ensure on access refresh the results is active
        self._db_loaded = False
        self._db_deleted = False
        await post_fn(
            real_class,
            model_instance=self,
            instance=instance,
            column_values=column_values,
            values=kwargs,
        )

    async def real_save(
        self,
        force_insert: bool,
        values: dict[str, Any] | set[str] | None,
    ) -> Self:
        """
        Performs the actual save operation, determining whether to insert or update.

        This method checks for the existence of the instance in the database and
        decides whether to perform an `_insert` or `_update` operation. It also
        handles pre-save and post-save signals.

        Args:
            force_insert: If True, forces an insert operation regardless of whether
                          the instance already exists in the database.
            values: A dictionary of specific values to save, or a set of field
                    names to explicitly mark as modified for a partial update.
                    If None, all extracted database fields are considered.

        Returns:
            The saved model instance.
        """
        instance: BaseModelType | QuerySet = CURRENT_INSTANCE.get()
        extracted_fields = self.extract_db_fields()
        if values is None:
            explicit_values: set[str] = set()
        elif isinstance(values, set):
            # special mode for marking values as explicit values
            explicit_values = set(values)
            values = None
        else:
            explicit_values = set(values.keys())

        token = MODEL_GETATTR_BEHAVIOR.set("coro")
        try:
            for pkcolumn in type(self).pkcolumns:
                # should trigger load in case of identifying_db_fields
                value = getattr(self, pkcolumn, None)
                if inspect.isawaitable(value):
                    value = await value
                if value is None and self.table.columns[pkcolumn].autoincrement:
                    extracted_fields.pop(pkcolumn, None)
                    force_insert = True
                field = self.meta.fields.get(pkcolumn)
                # this is an IntegerField/DateTime with primary_key set
                if field is not None:
                    if getattr(field, "increment_on_save", 0) != 0 or getattr(
                        field, "auto_now", False
                    ):
                        # we create a new revision.
                        force_insert = True
                    elif getattr(field, "auto_now_add", False):  # noqa: SIM102
                        # force_insert if auto_now_add field is empty
                        if value is None:
                            force_insert = True

            # check if it exists
            if not force_insert and not await self.check_exist_in_db(only_needed=True):
                force_insert = True
        finally:
            MODEL_GETATTR_BEHAVIOR.reset(token)

        token2 = EXPLICIT_SPECIFIED_VALUES.set(explicit_values)
        try:
            if force_insert:
                if values:
                    extracted_fields.update(values)
                # force save must ensure a complete mapping
                await self._insert(
                    bool(values),
                    extracted_fields,
                    pre_fn=partial(
                        self.meta.signals.pre_save.send_async, is_update=False, is_migration=False
                    ),
                    post_fn=partial(
                        self.meta.signals.post_save.send_async, is_update=False, is_migration=False
                    ),
                    instance=instance,
                )
            else:
                await self._update(
                    # assume partial when values are None
                    values is not None,
                    extracted_fields if values is None else values,
                    pre_fn=partial(
                        self.meta.signals.pre_save.send_async, is_update=True, is_migration=False
                    ),
                    post_fn=partial(
                        self.meta.signals.post_save.send_async, is_update=True, is_migration=False
                    ),
                    instance=instance,
                )
        finally:
            EXPLICIT_SPECIFIED_VALUES.reset(token2)
        return self

    async def save(
        self: Model,
        force_insert: bool = False,
        values: dict[str, Any] | set[str] | None = None,
        force_save: bool | None = None,
    ) -> Model:
        """
        Saves the current model instance to the database.

        This method acts as a public entry point for saving, encapsulating the
        logic for deciding between an insert or update operation. It also handles
        context variable management for the save process.

        Args:
            force_insert: If True, forces an insert operation even if the instance
                          might already exist.
            values: A dictionary of specific values to save, or a set of field
                    names to explicitly mark as modified for a partial update.
                    If None, all extracted database fields are considered.
            force_save: Deprecated. Use `force_insert` instead.

        Returns:
            The saved model instance.
        """
        if force_save is not None:
            warnings.warn(
                "'force_save' is deprecated in favor of 'force_insert'",
                DeprecationWarning,
                stacklevel=2,
            )
            force_insert = force_save
        token = CURRENT_INSTANCE.set(self)
        try:
            return await self.real_save(force_insert=force_insert, values=values)
        finally:
            CURRENT_INSTANCE.reset(token)

    @classmethod
    def build(
        cls,
        schema: str | None = None,
        metadata: sqlalchemy.MetaData | None = None,
    ) -> sqlalchemy.Table:
        """
        Builds and returns the SQLAlchemy table representation for the model.

        This method constructs the `sqlalchemy.Table` object, including columns,
        unique constraints, indexes, and global constraints, based on the model's
        meta information and specified schema.

        Args:
            schema: An optional schema name to apply to the table.
            metadata: An optional `sqlalchemy.MetaData` object to use. If None,
                      the registry's metadata is used.

        Returns:
            The constructed SQLAlchemy `Table` object.

        Raises:
            AssertionError: If the model's registry is not set.
        """
        tablename: str = cls.meta.tablename
        registry = cls.meta.registry
        assert registry, "registry is not set"
        if metadata is None:
            metadata = registry.metadata_by_url[str(cls.database.url)]
        schemes: list[str] = []
        if schema:
            schemes.append(schema)
        if cls.__using_schema__ is not Undefined:
            schemes.append(cls.__using_schema__)
        db_schema = cls.get_db_schema() or ""
        schemes.append(db_schema)

        unique_together = cls.meta.unique_together
        index_constraints = cls.meta.indexes

        columns: list[sqlalchemy.Column] = []
        global_constraints: list[sqlalchemy.Constraint] = [
            copy.copy(constraint) for constraint in cls.meta.constraints
        ]
        for name, field in cls.meta.fields.items():
            current_columns = field.get_columns(name)
            columns.extend(current_columns)
            if not NO_GLOBAL_FIELD_CONSTRAINTS.get():
                global_constraints.extend(
                    field.get_global_constraints(name, current_columns, schemes)
                )

        # Handle the uniqueness together
        uniques = []
        for unique_index in unique_together:
            unique_constraint = cls._get_unique_constraints(unique_index)
            uniques.append(unique_constraint)

        # Handle the indexes
        indexes = []
        for index_c in index_constraints:
            index = cls._get_indexes(index_c)
            indexes.append(index)
        return sqlalchemy.Table(
            tablename,
            metadata,
            *columns,
            *uniques,
            *indexes,
            *global_constraints,
            extend_existing=True,
            schema=(
                schema
                if schema
                else cls.get_active_class_schema(check_schema=False, check_tenant=False)
            ),
        )

    @classmethod
    def add_global_field_constraints(
        cls,
        schema: str | None = None,
        metadata: sqlalchemy.MetaData | None = None,
    ) -> sqlalchemy.Table:
        """
        Adds global constraints to an existing SQLAlchemy table.

        This method is particularly useful for applying schema-specific or
        tenant-specific constraints to a table that has already been built.

        Args:
            schema: An optional schema name associated with the table.
            metadata: An optional `sqlalchemy.MetaData` object. If None,
                      the registry's metadata is used.

        Returns:
            The SQLAlchemy `Table` object with the added constraints.

        Raises:
            AssertionError: If the model's registry is not set.
        """
        tablename: str = cls.meta.tablename
        registry = cls.meta.registry
        assert registry, "registry is not set"
        if metadata is None:
            metadata = registry.metadata_by_url[str(cls.database.url)]
        schemes: list[str] = []
        if schema:
            schemes.append(schema)
        if cls.__using_schema__ is not Undefined:
            schemes.append(cls.__using_schema__)
        db_schema = cls.get_db_schema() or ""
        schemes.append(db_schema)
        table = metadata.tables[tablename if not schema else f"{schema}.{tablename}"]
        for name, field in cls.meta.fields.items():
            current_columns: list[sqlalchemy.Column] = []
            for column_name in cls.meta.field_to_column_names[name]:
                current_columns.append(table.columns[column_name])
            for constraint in field.get_global_constraints(name, current_columns, schemes):
                table.append_constraint(constraint)
        return table

    @classmethod
    def _get_unique_constraints(
        cls, fields: Collection[str] | str | UniqueConstraint
    ) -> sqlalchemy.UniqueConstraint | None:
        """
        Constructs and returns a SQLAlchemy `UniqueConstraint` object.

        This method handles different input types for defining unique constraints,
        including a single field name, a collection of field names, or a
        `UniqueConstraint` object. It also generates a unique name for the constraint
        if not explicitly provided.

        Args:
            fields: The fields (or a `UniqueConstraint` object) for which to create
                    the unique constraint.

        Returns:
            A SQLAlchemy `UniqueConstraint` object, or None if no fields are provided.
        """
        if isinstance(fields, str):
            return sqlalchemy.UniqueConstraint(
                *cls.meta.field_to_column_names[fields],
                name=hash_names([fields], inner_prefix=cls.__name__, outer_prefix="uc"),
            )
        elif isinstance(fields, UniqueConstraint):
            return sqlalchemy.UniqueConstraint(
                *chain.from_iterable(
                    # deduplicate and extract columns
                    cls.meta.field_to_column_names[field]
                    for field in set(fields.fields)
                ),
                name=fields.name,
                deferrable=fields.deferrable,
                initially=fields.initially,
            )
        # deduplicate
        fields = set(fields)
        return sqlalchemy.UniqueConstraint(
            *chain.from_iterable(cls.meta.field_to_column_names[field] for field in fields),
            name=hash_names(fields, inner_prefix=cls.__name__, outer_prefix="uc"),
        )

    @classmethod
    def _get_indexes(cls, index: Index) -> sqlalchemy.Index | None:
        """
        Constructs and returns a SQLAlchemy `Index` object based on an `Index` definition.

        Args:
            index: The `Index` object containing the fields and name for the index.

        Returns:
            A SQLAlchemy `Index` object.
        """
        return sqlalchemy.Index(
            index.name,
            *chain.from_iterable(
                (
                    [field]
                    if isinstance(field, sqlalchemy.TextClause)
                    else cls.meta.field_to_column_names[field]
                )
                for field in index.fields
            ),
        )

    def not_set_transaction(self, *, force_rollback: bool = False, **kwargs: Any) -> Transaction:
        """
        Returns a database transaction for the assigned database.

        This method is designed to be assigned as the `transaction` property for
        model instances, allowing them to initiate database transactions.

        Args:
            force_rollback: If True, forces the transaction to roll back.
            **kwargs: Additional keyword arguments to pass to the database's
                      transaction method.

        Returns:
            A `Transaction` object.
        """
        return cast(
            "Transaction",
            self.database.transaction(force_rollback=force_rollback, **kwargs),
        )
