from __future__ import annotations

import contextlib
import copy
import inspect
import warnings
from collections.abc import Awaitable, Callable, Collection, Sequence
from functools import partial
from itertools import chain
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Optional, Union, cast

import sqlalchemy
from pydantic import BaseModel

from edgy.core.db.constants import CASCADE
from edgy.core.db.context_vars import (
    CURRENT_INSTANCE,
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

if TYPE_CHECKING:
    from databasez.core.transaction import Transaction

    from edgy.core.connection.database import Database
    from edgy.core.connection.registry import Registry
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.model import Model


_empty = cast(set[str], frozenset())


class _EmptyClass: ...


_removed_copy_keys = {
    *BaseModel.__dict__.keys(),
    "_loaded_or_deleted",
    "_pkcolumns",
    "_table",
    "_db_schemas",
    "__proxy_model__",
    "meta",
}
_removed_copy_keys.difference_update(
    {*_EmptyClass.__dict__.keys(), "__annotations__", "__module__"}
)


def _check_replace_related_field(
    replace_related_field: Union[
        bool,
        type[BaseModelType],
        tuple[type[BaseModelType], ...],
        list[type[BaseModelType]],
    ],
    model: type[BaseModelType],
) -> bool:
    if isinstance(replace_related_field, bool):
        return replace_related_field
    if not isinstance(replace_related_field, (tuple, list)):
        replace_related_field = (replace_related_field,)
    return any(refmodel is model for refmodel in replace_related_field)


def _set_related_field(
    target: type[BaseModelType],
    *,
    foreign_key_name: str,
    related_name: str,
    source: type[BaseModelType],
    replace_related_field: Union[
        bool,
        type[BaseModelType],
        tuple[type[BaseModelType], ...],
        list[type[BaseModelType]],
    ],
) -> None:
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
                f"Multiple related_name with the same value '{related_name}' found to the same target. Related names must be different."
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
    replace_related_field: Union[
        bool,
        type[BaseModelType],
        tuple[type[BaseModelType], ...],
        list[type[BaseModelType]],
    ] = False,
) -> None:
    """
    Sets the related name for the foreign keys.
    When a `related_name` is generated, creates a RelatedField from the table pointed
    from the ForeignKey declaration and the the table declaring it.
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
        # foreign_key.__dict__.pop("target", None)
        # foreign_key.__dict__.pop("target_registry", None)
        registry: Registry = foreign_key.target_registry
        with contextlib.suppress(Exception):
            registry = cast("Registry", foreign_key.target.registry)
        registry.register_callback(foreign_key.to, related_field_fn, one_time=True)


class DatabaseMixin:
    _removed_copy_keys: ClassVar[set[str]] = _removed_copy_keys

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.transaction = self.not_set_transaction

    @classmethod
    def real_add_to_registry(
        cls: type[BaseModelType],
        *,
        registry: Registry,
        registry_type_name: str = "models",
        name: str = "",
        database: Union[bool, Database, Literal["keep"]] = "keep",
        replace_related_field: Union[
            bool,
            type[BaseModelType],
            tuple[type[BaseModelType], ...],
            list[type[BaseModelType]],
        ] = False,
        on_conflict: Literal["keep", "replace", "error"] = "error",
    ) -> type[BaseModelType]:
        """For customizations."""
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
                registry.execute_model_callbacks(cls)

        # finalize
        cls.model_rebuild(force=True)
        return cls

    @classmethod
    def add_to_registry(
        cls,
        registry: Registry,
        name: str = "",
        database: Union[bool, Database, Literal["keep"]] = "keep",
        *,
        replace_related_field: Union[
            bool,
            type[BaseModelType],
            tuple[type[BaseModelType], ...],
            list[type[BaseModelType]],
        ] = False,
        on_conflict: Literal["keep", "replace", "error"] = "error",
    ) -> type[BaseModelType]:
        return cls.real_add_to_registry(
            registry=registry,
            name=name,
            database=database,
            replace_related_field=replace_related_field,
            on_conflict=on_conflict,
        )

    def get_active_instance_schema(
        self, check_schema: bool = True, check_tenant: bool = True
    ) -> Union[str, None]:
        if self._edgy_namespace["__using_schema__"] is not Undefined:
            return cast(Union[str, None], self._edgy_namespace["__using_schema__"])
        return type(self).get_active_class_schema(
            check_schema=check_schema, check_tenant=check_tenant
        )

    @classmethod
    def get_active_class_schema(cls, check_schema: bool = True, check_tenant: bool = True) -> str:
        if cls.__using_schema__ is not Undefined:
            return cast(Union[str, None], cls.__using_schema__)
        if check_schema:
            schema = get_schema(check_tenant=check_tenant)
            if schema is not None:
                return schema
        db_schema: Optional[str] = cls.get_db_schema()
        # sometime "" is ok, sometimes not, sqlalchemy logic
        return db_schema or None

    @classmethod
    def copy_edgy_model(
        cls: type[Model],
        registry: Optional[Registry] = None,
        name: str = "",
        unlink_same_registry: bool = True,
        on_conflict: Literal["keep", "replace", "error"] = "error",
        **kwargs: Any,
    ) -> type[Model]:
        """Copy the model class and optionally add it to another registry."""
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
                        through_model.meta.fields[src_field.from_foreign_key].related_name = cast(
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
        return _copy

    @property
    def table(self) -> sqlalchemy.Table:
        if self._edgy_namespace.get("_table") is None:
            schema = self.get_active_instance_schema()
            return cast(
                "sqlalchemy.Table",
                type(self).table_schema(schema),
            )
        return cast("sqlalchemy.Table", self._edgy_namespace["_table"])

    @table.setter
    def table(self, value: Optional[sqlalchemy.Table]) -> None:
        self._edgy_namespace.pop("_pkcolumns", None)
        self._edgy_namespace["_table"] = value

    @table.deleter
    def table(self) -> None:
        self._edgy_namespace.pop("_pkcolumns", None)
        self._edgy_namespace.pop("_table", None)

    @property
    def pkcolumns(self) -> Sequence[str]:
        if self._edgy_namespace.get("_pkcolumns") is None:
            if self._edgy_namespace.get("_table") is None:
                self._edgy_namespace["_pkcolumns"] = type(self).pkcolumns
            else:
                self._edgy_namespace["_pkcolumns"] = build_pkcolumns(self)
        return cast(Sequence[str], self._edgy_namespace["_pkcolumns"])

    @property
    def pknames(self) -> Sequence[str]:
        return cast(Sequence[str], type(self).pknames)

    def __setattr__(self, key: str, value: Any) -> None:
        if key == "__using_schema__":
            self._edgy_namespace.pop("_table", None)
        super().__setattr__(key, value)

    def get_columns_for_name(self: Model, name: str) -> Sequence[sqlalchemy.Column]:
        table = self.table
        meta = self.meta
        if name in meta.field_to_columns:
            return meta.field_to_columns[name]
        elif name in table.columns:
            return (table.columns[name],)
        else:
            return cast(Sequence["sqlalchemy.Column"], _empty)

    def identifying_clauses(self, prefix: str = "") -> list[Any]:
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
        pre_fn: Callable[..., Awaitable],
        post_fn: Callable[..., Awaitable],
    ) -> Any:
        """
        Update operation of the database fields.
        """
        column_values = self.extract_column_values(
            extracted_values=kwargs,
            is_partial=is_partial,
            is_update=True,
            phase="prepare_update",
            instance=self,
            model_instance=self,
            evaluate_values=True,
        )
        await pre_fn(self.__class__, instance=self, values=kwargs, column_values=column_values)
        # empty updates shouldn't cause an error. E.g. only model references are updated
        clauses = self.identifying_clauses()
        token = CURRENT_INSTANCE.set(self)
        try:
            if column_values and clauses:
                check_db_connection(self.database, stacklevel=4)
                async with self.database as database, database.transaction():
                    # can update column_values
                    column_values.update(
                        await self.execute_pre_save_hooks(
                            column_values, kwargs, force_insert=False
                        )
                    )
                    expression = self.table.update().values(**column_values).where(*clauses)
                    await database.execute(expression)

                # Update the model instance.
                new_kwargs = self.transform_input(
                    column_values, phase="post_update", instance=self
                )
                self.__dict__.update(new_kwargs)

            # updates aren't required to change the db, they can also just affect the meta fields
            await self.execute_post_save_hooks(
                cast(Sequence[str], kwargs.keys()), force_insert=False
            )

        finally:
            CURRENT_INSTANCE.reset(token)
        if column_values or kwargs:
            # Ensure on access refresh the results is active
            self._loaded_or_deleted = False
        await post_fn(self.__class__, instance=self, values=kwargs, column_values=column_values)

    async def update(self: Model, **kwargs: Any) -> Model:
        token = EXPLICIT_SPECIFIED_VALUES.set(set(kwargs.keys()))
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
            )
        finally:
            EXPLICIT_SPECIFIED_VALUES.reset(token)
        return self

    async def delete(
        self, skip_post_delete_hooks: bool = False, remove_referenced_call: bool = False
    ) -> None:
        """Delete operation from the database"""
        await self.meta.signals.pre_delete.send_async(self.__class__, instance=self)
        # get values before deleting
        field_values: dict[str, Any] = {}
        if not skip_post_delete_hooks and self.meta.post_delete_fields:
            token = MODEL_GETATTR_BEHAVIOR.set("coro")
            try:
                for field_name in self.meta.post_delete_fields:
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
                row_count = await database.execute(expression)
        # we cannot load anymore
        self._loaded_or_deleted = True
        # now cleanup with the saved values
        for field_name, value in field_values.items():
            field = self.meta.fields[field_name]
            await field.post_delete_callback(value, instance=self)

        await self.meta.signals.post_delete.send_async(
            self.__class__, instance=self, row_count=row_count
        )

    async def load(self, only_needed: bool = False) -> None:
        if only_needed and self._loaded_or_deleted:
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
            raise ObjectNotFound("row does not exist anymore")
        # Update the instance.
        self.__dict__.update(self.transform_input(dict(row._mapping), phase="load", instance=self))
        self._loaded_or_deleted = True

    async def _insert(
        self: Model,
        evaluate_values: bool,
        kwargs: dict[str, Any],
        pre_fn: Callable[..., Awaitable],
        post_fn: Callable[..., Awaitable],
    ) -> Model:
        """
        Performs the save instruction.
        """
        column_values: dict[str, Any] = self.extract_column_values(
            extracted_values=kwargs,
            is_partial=False,
            is_update=False,
            phase="prepare_insert",
            instance=self,
            model_instance=self,
            evaluate_values=evaluate_values,
        )
        await pre_fn(self.__class__, instance=self, column_values=column_values, values=kwargs)
        check_db_connection(self.database, stacklevel=4)
        token = CURRENT_INSTANCE.set(self)
        try:
            async with self.database as database, database.transaction():
                # can update column_values
                column_values.update(
                    await self.execute_pre_save_hooks(column_values, kwargs, force_insert=True)
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
                await self.execute_post_save_hooks(
                    cast(Sequence[str], kwargs.keys()), force_insert=True
                )
        finally:
            CURRENT_INSTANCE.reset(token)
        # Ensure on access refresh the results is active
        self._loaded_or_deleted = False
        await post_fn(self.__class__, instance=self, column_values=column_values, values=kwargs)

        return self

    async def save(
        self: Model,
        force_insert: bool = False,
        values: Union[dict[str, Any], set[str], None] = None,
        force_save: Optional[bool] = None,
    ) -> Model:
        """
        Performs a save of a given model instance.
        When creating a user it will make sure it can update existing or
        create a new one.
        """
        if force_save is not None:
            warnings.warn(
                "'force_save' is deprecated in favor of 'force_insert'",
                DeprecationWarning,
                stacklevel=2,
            )
            force_insert = force_save

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
                # this is an IntegerField with primary_key set
                if field is not None and getattr(field, "increment_on_save", 0) != 0:
                    # we create a new revision.
                    force_insert = True
                    # Note: we definitely want this because it is easy for forget a force_insert
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
                )
        finally:
            EXPLICIT_SPECIFIED_VALUES.reset(token2)
        return self

    @classmethod
    def build(
        cls,
        schema: Optional[str] = None,
        metadata: Optional[sqlalchemy.MetaData] = None,
    ) -> sqlalchemy.Table:
        """
        Builds the SQLAlchemy table representation from the loaded fields.
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
        schema: Optional[str] = None,
        metadata: Optional[sqlalchemy.MetaData] = None,
    ) -> sqlalchemy.Table:
        """
        Add global constraints to table. Required for tenants.
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
        cls, fields: Union[Collection[str], str, UniqueConstraint]
    ) -> Optional[sqlalchemy.UniqueConstraint]:
        """
        Returns the unique constraints for the model.

        The columns must be a a list, tuple of strings or a UniqueConstraint object.

        :return: Model UniqueConstraint.
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
    def _get_indexes(cls, index: Index) -> Optional[sqlalchemy.Index]:
        """
        Creates the index based on the Index fields
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
        Return database transaction for the assigned database.

        This method is automatically assigned to transaction masking the metaclass transaction for instances.
        """
        return cast(
            "Transaction",
            self.database.transaction(force_rollback=force_rollback, **kwargs),
        )
