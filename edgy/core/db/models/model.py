import copy
import inspect
import warnings
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Optional, Union, cast

from edgy.core.db.context_vars import (
    CURRENT_INSTANCE,
    EXPLICIT_SPECIFIED_VALUES,
    MODEL_GETATTR_BEHAVIOR,
)
from edgy.core.db.models.base import EdgyBaseModel
from edgy.core.db.models.mixins import DeclarativeMixin, ModelRowMixin, ReflectedModelMixin
from edgy.core.db.models.model_proxy import ProxyModel
from edgy.core.utils.db import check_db_connection
from edgy.core.utils.models import generify_model_fields
from edgy.exceptions import ObjectNotFound

if TYPE_CHECKING:
    from databasez.core.transaction import Transaction


class Model(ModelRowMixin, DeclarativeMixin, EdgyBaseModel):
    """
    Representation of an Edgy `Model`.

    This also means it can generate declarative SQLAlchemy models
    from anywhere by calling the `Model.declarative()` function.

    **Example**

    ```python
    import edgyBaseFieldType
    from edgy import Database, Registry

    database = Database("sqlite:///db.sqlite")
    models = Registry(database=database)


    class User(edgy.Model):
        '''
        The User model to be created in the database as a table
        If no name is provided the in Meta class, it will generate
        a "users" table for you.
        '''

        id: int = edgy.IntegerField(primary_key=True)
        is_active: bool = edgy.BooleanField(default=False)

        class Meta:
            registry = models
    ```
    """

    class Meta:
        abstract = True

    @classmethod
    def generate_proxy_model(cls) -> type["Model"]:
        """
        Generates a proxy model for each model. This proxy model is a simple
        shallow copy of the original model being generated.
        """
        fields = {key: copy.copy(field) for key, field in cls.meta.fields.items()}

        class MethodHolder(Model):
            pass

        ignore = set(dir(MethodHolder))

        for key in dir(cls):
            if key in ignore or key.startswith("_"):
                continue
            val = inspect.getattr_static(cls, key)
            if inspect.isfunction(val):
                setattr(MethodHolder, key, val)

        proxy_model = ProxyModel(
            name=cls.__name__,
            module=cls.__module__,
            metadata=cls.meta,
            definitions=fields,
            bases=(MethodHolder,),
        )

        proxy_model.build()
        generify_model_fields(cast(type[EdgyBaseModel], proxy_model.model))
        return cast(type[Model], proxy_model.model)

    async def _update(self, **kwargs: Any) -> Any:
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
                check_db_connection(self.database)
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
                for k, v in new_kwargs.items():
                    setattr(self, k, v)

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

    async def update(self, **kwargs: Any) -> "Model":
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

    async def _insert(self, **kwargs: Any) -> "Model":
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
        check_db_connection(self.database)
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
            for k, v in new_kwargs.items():
                setattr(self, k, v)

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
        self,
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

    def transaction(self, *, force_rollback: bool = False, **kwargs: Any) -> "Transaction":
        """Return database transaction for the assigned database"""
        return self.database.transaction(force_rollback=force_rollback, **kwargs)


class ReflectModel(ReflectedModelMixin, Model):
    """
    Reflect on async engines is not yet supported, therefore, we need to make a sync_engine
    call.
    """

    class Meta:
        abstract = True
