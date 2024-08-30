import inspect
from typing import TYPE_CHECKING, Any, Dict, Optional, Union, cast

from sqlalchemy.engine.result import Row

from edgy.core.db.context_vars import MODEL_GETATTR_BEHAVIOR
from edgy.core.db.models.base import EdgyBaseModel
from edgy.core.db.models.mixins import DeclarativeMixin, ModelRowMixin, ReflectedModelMixin
from edgy.exceptions import ObjectNotFound

if TYPE_CHECKING:
    pass


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

        # empty updates shouldn't cause an error
        if kwargs:
            kwargs = self.extract_column_values(
                extracted_values=kwargs, is_partial=True, is_update=True
            )
            expression = self.table.update().values(**kwargs).where(*self.identifying_clauses())
            await self.database.execute(expression)
        await self.meta.signals.post_update.send_async(self.__class__, instance=self)

        # Update the model instance.
        for key, value in kwargs.items():
            setattr(self, key, value)

        token = MODEL_GETATTR_BEHAVIOR.set("coro")
        try:
            for field_name in self.meta.post_save_fields:
                field = self.meta.fields[field_name]
                try:
                    value = getattr(self, field_name)
                except AttributeError:
                    continue
                if inspect.isawaitable(value):
                    value = await value
                await field.post_save_callback(value, instance=self)
        finally:
            MODEL_GETATTR_BEHAVIOR.reset(token)
        return self

    async def delete(self) -> None:
        """Delete operation from the database"""
        await self.meta.signals.pre_delete.send_async(self.__class__, instance=self)

        expression = self.table.delete().where(*self.identifying_clauses())
        await self.database.execute(expression)
        # we cannot load anymore
        self._loaded_or_deleted = True

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
        expression = self.table.insert().values(**kwargs)
        autoincrement_value = cast(Optional["Row"], await self.database.execute(expression))
        transformed_kwargs = self.transform_input(kwargs, phase="post_insert", instance=self)
        for k, v in transformed_kwargs.items():
            setattr(self, k, v)
        # sqlalchemy supports only one autoincrement column
        if autoincrement_value:
            column = self.table.autoincrement_column
            if column is not None and isinstance(autoincrement_value, Row):
                autoincrement_value = autoincrement_value._mapping[column.name]
            # can be explicit set, which causes an invalid value returned
            if column is not None and column.key not in kwargs:
                setattr(self, column.key, autoincrement_value)

        token = MODEL_GETATTR_BEHAVIOR.set("coro")
        try:
            for field_name in self.meta.post_save_fields:
                field = self.meta.fields[field_name]
                try:
                    value = getattr(self, field_name)
                except AttributeError:
                    continue
                if inspect.isawaitable(value):
                    value = await value
                await field.post_save_callback(value, instance=self)
        finally:
            MODEL_GETATTR_BEHAVIOR.reset(token)
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

        for pkcolumn in self.__class__.pkcolumns:
            # should trigger load in case of identifying_db_fields
            if (
                getattr(self, pkcolumn, None) is None
                and self.table.columns[pkcolumn].autoincrement
            ):
                extracted_fields.pop(pkcolumn, None)
                force_save = True

        if force_save:
            if values:
                extracted_fields.update(values)
            # force save must ensure a complete mapping
            kwargs = self.extract_column_values(
                extracted_values=extracted_fields, is_partial=False, is_update=False
            )
            await self._save(**kwargs)
        else:
            # Broadcast the initial update details
            # Making sure it only updates the fields that should be updated
            # and excludes the fields with `auto_now` as true
            kwargs = self.extract_column_values(
                extracted_values=extracted_fields if values is None else values,
                is_update=True,
                is_partial=values is not None,
            )

            await self.meta.signals.pre_update.send_async(
                self.__class__, instance=self, kwargs=kwargs
            )
            await self.update(**kwargs)

            # Broadcast the update complete
            await self.meta.signals.post_update.send_async(self.__class__, instance=self)

        # Ensure on access refresh the results is active
        self._loaded_or_deleted = False

        await self.meta.signals.post_save.send_async(self.__class__, instance=self)
        return self


class ReflectModel(ReflectedModelMixin, Model):
    """
    Reflect on async engines is not yet supported, therefore, we need to make a sync_engine
    call.
    """

    class Meta:
        abstract = True
