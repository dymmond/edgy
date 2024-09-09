import inspect
from typing import Any, Dict, Union

from edgy.core.db.context_vars import MODEL_GETATTR_BEHAVIOR
from edgy.core.db.models.base import EdgyBaseModel
from edgy.core.db.models.mixins import DeclarativeMixin, ModelRowMixin, ReflectedModelMixin
from edgy.exceptions import ObjectNotFound


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

    async def update(self, **kwargs: Any) -> Any:
        """
        Update operation of the database fields.
        """
        await self.meta.signals.pre_update.send_async(self.__class__, instance=self)
        column_values = self.extract_column_values(
            extracted_values=kwargs, is_partial=True, is_update=True
        )

        # empty updates shouldn't cause an error. E.g. only model references are updated
        if column_values:
            async with self.database.transaction():
                # can update column_values
                await self.execute_pre_save_hooks(column_values)
                expression = (
                    self.table.update().values(**column_values).where(*self.identifying_clauses())
                )
                await self.database.execute(expression)

            # Update the model instance.
            new_kwargs = self.transform_input(column_values, phase="post_update", instance=self)
            for k, v in new_kwargs.items():
                setattr(self, k, v)

        # updates aren't required to change the db, they can also just affect the meta fields
        await self.execute_post_save_hooks(kwargs.keys())
        if kwargs:
            # Ensure on access refresh the results is active
            self._loaded_or_deleted = False
        await self.meta.signals.post_update.send_async(self.__class__, instance=self)

        return self

    async def delete(self, skip_post_delete_hooks: bool = False) -> None:
        """Delete operation from the database"""
        await self.meta.signals.pre_delete.send_async(self.__class__, instance=self)
        # get values before deleting
        field_values: Dict[str, Any] = {}
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
        expression = self.table.delete().where(*self.identifying_clauses())
        await self.database.execute(expression)
        # we cannot load anymore
        self._loaded_or_deleted = True
        # now cleanup with the saved values
        for field_name, value in field_values.items():
            field = self.meta.fields[field_name]
            await field.post_delete_callback(value)

        await self.meta.signals.post_delete.send_async(self.__class__, instance=self)

    async def load(self, only_needed: bool = False) -> None:
        if only_needed and self._loaded_or_deleted:
            return
        # Build the select expression.
        expression = self.table.select().where(*self.identifying_clauses())

        # Perform the fetch.
        row = await self.database.fetch_one(expression)
        # check if is in system
        if row is None:
            raise ObjectNotFound("row does not exist anymore")
        # Update the instance.
        self.__dict__.update(self.transform_input(dict(row._mapping), phase="load", instance=self))
        self._loaded_or_deleted = True

    async def _save(self, **kwargs: Any) -> "Model":
        """
        Performs the save instruction.
        """
        column_values = self.extract_column_values(
            extracted_values=kwargs, is_partial=False, is_update=False
        )
        async with self.database.transaction():
            # can update column_values
            await self.execute_pre_save_hooks(column_values)
            expression = self.table.insert().values(**column_values)
            autoincrement_value = await self.database.execute(expression)
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
            await self.execute_post_save_hooks(kwargs.keys())
        # Ensure on access refresh the results is active
        self._loaded_or_deleted = False

        return self

    async def save(
        self,
        force_save: bool = False,
        values: Dict[str, Any] = None,
        **kwargs: Any,
    ) -> Union["Model", Any]:
        """
        Performs a save of a given model instance.
        When creating a user it will make sure it can update existing or
        create a new one.
        """
        await self.meta.signals.pre_save.send_async(self.__class__, instance=self)

        extracted_fields = self.extract_db_fields()

        token = MODEL_GETATTR_BEHAVIOR.set("coro")
        try:
            for pkcolumn in self.__class__.pkcolumns:
                # should trigger load in case of identifying_db_fields
                value = getattr(self, pkcolumn, None)
                if inspect.isawaitable(value):
                    value = await value
                if value is None and self.table.columns[pkcolumn].autoincrement:
                    extracted_fields.pop(pkcolumn, None)
                    force_save = True
        finally:
            MODEL_GETATTR_BEHAVIOR.reset(token)

        if force_save:
            if values:
                extracted_fields.update(values)
            # force save must ensure a complete mapping
            await self._save(**extracted_fields)
        else:
            await self.update(**(extracted_fields if values is None else values))

        await self.meta.signals.post_save.send_async(self.__class__, instance=self)
        return self


class ReflectModel(ReflectedModelMixin, Model):
    """
    Reflect on async engines is not yet supported, therefore, we need to make a sync_engine
    call.
    """

    class Meta:
        abstract = True
