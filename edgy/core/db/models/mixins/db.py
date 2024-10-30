import contextlib
import inspect
import warnings
from collections.abc import Sequence
from functools import partial
from typing import TYPE_CHECKING, Any, Literal, Optional, Union, cast

import sqlalchemy
from pydantic import BaseModel

from edgy.core.db.context_vars import (
    CURRENT_INSTANCE,
    EXPLICIT_SPECIFIED_VALUES,
    MODEL_GETATTR_BEHAVIOR,
    get_schema,
)
from edgy.core.db.datastructures import Index, UniqueConstraint
from edgy.core.db.fields.many_to_many import BaseManyToManyForeignKeyField
from edgy.core.db.models.metaclasses import MetaInfo
from edgy.core.db.models.utils import build_pkcolumns, build_pknames
from edgy.core.db.relationships.related_field import RelatedField
from edgy.core.utils.db import check_db_connection
from edgy.exceptions import ForeignKeyBadConfigured, ObjectNotFound
from edgy.types import Undefined

if TYPE_CHECKING:
    from databasez.core.transaction import Transaction

    from edgy.core.connection.database import Database
    from edgy.core.connection.registry import Registry
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.model import Model
    from edgy.core.db.models.types import BaseModelType


_empty = cast(set[str], frozenset())


def _set_related_field(
    target: type["BaseModelType"],
    *,
    foreign_key_name: str,
    related_name: str,
    source: type["BaseModelType"],
    replace_related_field: bool,
) -> None:
    if not replace_related_field and related_name in target.meta.fields:
        # is already correctly set, required for migrate of model_apps with registry set
        related_field = target.meta.fields[related_name]
        if (
            related_field.related_from is source
            and related_field.foreign_key_name == foreign_key_name
        ):
            return
        raise ForeignKeyBadConfigured(
            f"Multiple related_name with the same value '{related_name}' found to the same target. Related names must be different."
        )

    related_field = RelatedField(
        foreign_key_name=foreign_key_name,
        name=related_name,
        owner=target,
        related_from=source,
    )

    # Set the related name
    target.meta.fields[related_name] = related_field


def _set_related_name_for_foreign_keys(
    meta: "MetaInfo", model_class: type["BaseModelType"], replace_related_field: bool = False
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
        registry: Registry = foreign_key.target_registry
        with contextlib.suppress(Exception):
            registry = cast("Registry", foreign_key.target.registry)
        registry.register_callback(foreign_key.to, related_field_fn, one_time=True)


class DatabaseMixin:
    @classmethod
    def add_to_registry(
        cls: type["BaseModelType"],
        registry: "Registry",
        name: str = "",
        database: Union[bool, "Database", Literal["keep"]] = "keep",
    ) -> None:
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
            if getattr(cls, "__reflected__", False):
                registry.reflected[cls.__name__] = cls
            else:
                registry.models[cls.__name__] = cls
            # after registrating the own model
            for value in list(meta.fields.values()):
                if isinstance(value, BaseManyToManyForeignKeyField):
                    m2m_registry: Registry = value.target_registry
                    with contextlib.suppress(Exception):
                        m2m_registry = cast("Registry", value.target.registry)

                    def create_through_model(x: Any, field: "BaseFieldType" = value) -> None:
                        # we capture with field = ... the variable
                        field.create_through_model()

                    m2m_registry.register_callback(value.to, create_through_model, one_time=True)
            # Sets the foreign key fields
            if meta.foreign_key_fields:
                _set_related_name_for_foreign_keys(meta, cls)
            registry.execute_model_callbacks(cls)

        # finalize
        cls.model_rebuild(force=True)

    def get_active_instance_schema(
        self, check_schema: bool = True, check_tenant: bool = True
    ) -> Union[str, None]:
        if self.__using_schema__ is not Undefined:
            return cast(Union[str, None], self.__using_schema__)
        return self.__class__.get_active_class_schema(
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
        cls: type["Model"], registry: Optional["Registry"] = None, name: str = "", **kwargs: Any
    ) -> type["Model"]:
        """Copy the model class and optionally add it to another registry."""
        # removes private pydantic stuff, except the prefixed ones
        attrs = {
            key: val
            for key, val in cls.__dict__.items()
            if key not in BaseModel.__dict__ or key.startswith("__")
        }
        attrs.pop("meta", None)
        # managers and fields are gone, we have to readd them with the correct data
        attrs.update(cls.meta.fields)
        attrs.update(cls.meta.managers)
        _copy = cast(
            type["Model"],
            type(cls.__name__, cls.__bases__, attrs, skip_registry=True, **kwargs),
        )
        _copy.meta.model = _copy
        if name:
            _copy.__name__ = name
        if registry is not None:
            _copy.add_to_registry(registry)
        return _copy

    @property
    def table(self) -> sqlalchemy.Table:
        if getattr(self, "_table", None) is None:
            schema = self.get_active_instance_schema()
            return cast(
                "sqlalchemy.Table",
                self.__class__.table_schema(schema),
            )
        return self._table

    @table.setter
    def table(self, value: sqlalchemy.Table) -> None:
        with contextlib.suppress(AttributeError):
            del self._pknames
        with contextlib.suppress(AttributeError):
            del self._pkcolumns
        self._table = value

    @property
    def pkcolumns(self) -> Sequence[str]:
        if self.__dict__.get("_pkcolumns", None) is None:
            if self.__dict__.get("_table", None) is None:
                self._pkcolumns: Sequence[str] = cast(Sequence[str], self.__class__.pkcolumns)
            else:
                build_pkcolumns(self)
        return self._pkcolumns

    @property
    def pknames(self) -> Sequence[str]:
        if self.__dict__.get("_pknames", None) is None:
            if self.__dict__.get("_table", None) is None:
                self._pknames: Sequence[str] = cast(Sequence[str], self.__class__.pknames)
            else:
                build_pknames(self)
        return self._pknames

    def get_columns_for_name(self: "Model", name: str) -> Sequence["sqlalchemy.Column"]:
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

    async def _update(self: "Model", **kwargs: Any) -> Any:
        """
        Update operation of the database fields.
        """
        await self.meta.signals.pre_update.send_async(self.__class__, instance=self)
        column_values = self.extract_column_values(
            extracted_values=kwargs,
            is_partial=True,
            is_update=True,
            phase="prepare_update",
            instance=self,
            model_instance=self,
        )
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
        await self.meta.signals.post_update.send_async(self.__class__, instance=self)

    async def update(self: "Model", **kwargs: Any) -> "Model":
        token = EXPLICIT_SPECIFIED_VALUES.set(set(kwargs.keys()))
        try:
            await self._update(**kwargs)
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
                        continue
                    if inspect.isawaitable(field_value):
                        try:
                            field_value = await field_value
                        except AttributeError:
                            continue
                    field_values[field_name] = field_value
            finally:
                MODEL_GETATTR_BEHAVIOR.reset(token)
        clauses = self.identifying_clauses()
        if clauses:
            expression = self.table.delete().where(*clauses)
            check_db_connection(self.database)
            async with self.database as database:
                await database.execute(expression)
        # we cannot load anymore
        self._loaded_or_deleted = True
        # now cleanup with the saved values
        for field_name, value in field_values.items():
            field = self.meta.fields[field_name]
            await field.post_delete_callback(value, instance=self)

        await self.meta.signals.post_delete.send_async(self.__class__, instance=self)

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

    async def _insert(self: "Model", **kwargs: Any) -> "Model":
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
        )
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

        return self

    async def save(
        self: "Model",
        force_insert: bool = False,
        values: Union[dict[str, Any], set[str], None] = None,
        force_save: Optional[bool] = None,
    ) -> "Model":
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

        await self.meta.signals.pre_save.send_async(self.__class__, instance=self)

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
            for pkcolumn in self.__class__.pkcolumns:
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
                await self._insert(**extracted_fields)
            else:
                await self._update(**(extracted_fields if values is None else values))
        finally:
            EXPLICIT_SPECIFIED_VALUES.reset(token2)
        await self.meta.signals.post_save.send_async(self.__class__, instance=self)
        return self

    @classmethod
    def build(
        cls, schema: Optional[str] = None, metadata: Optional[sqlalchemy.MetaData] = None
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
        global_constraints: list[Any] = []
        for name, field in cls.meta.fields.items():
            current_columns = field.get_columns(name)
            columns.extend(current_columns)
            global_constraints.extend(field.get_global_constraints(name, current_columns, schemes))

        # Handle the uniqueness together
        uniques = []
        for unique_index in unique_together or []:
            unique_constraint = cls._get_unique_constraints(unique_index)
            uniques.append(unique_constraint)

        # Handle the indexes
        indexes = []
        for index_c in index_constraints or []:
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
            schema=schema
            if schema
            else cls.get_active_class_schema(check_schema=False, check_tenant=False),
        )

    @classmethod
    def _get_unique_constraints(
        cls, columns: Union[Sequence, str, sqlalchemy.UniqueConstraint]
    ) -> Optional[sqlalchemy.UniqueConstraint]:
        """
        Returns the unique constraints for the model.

        The columns must be a a list, tuple of strings or a UniqueConstraint object.

        :return: Model UniqueConstraint.
        """
        if isinstance(columns, str):
            return sqlalchemy.UniqueConstraint(columns)
        elif isinstance(columns, UniqueConstraint):
            return sqlalchemy.UniqueConstraint(*columns.fields, name=columns.name)
        return sqlalchemy.UniqueConstraint(*columns)

    @classmethod
    def _get_indexes(cls, index: Index) -> Optional[sqlalchemy.Index]:
        """
        Creates the index based on the Index fields
        """
        return sqlalchemy.Index(index.name, *index.fields)

    def transaction(self, *, force_rollback: bool = False, **kwargs: Any) -> "Transaction":
        """Return database transaction for the assigned database"""
        return cast(
            "Transaction", self.database.transaction(force_rollback=force_rollback, **kwargs)
        )
