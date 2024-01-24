from typing import Any, Dict, Set, Type, Union

from edgy.core.db.models.base import EdgyBaseReflectModel
from edgy.core.db.models.mixins import DeclarativeMixin
from edgy.core.db.models.row import ModelRow
from edgy.core.utils.functional import edgy_setattr
from edgy.core.utils.sync import run_sync
from edgy.exceptions import RelationshipNotFound


class Model(ModelRow, DeclarativeMixin):
    """
    Representation of an Edgy `Model`.

    This also means it can generate declarative SQLAlchemy models
    from anywhere by calling the `Model.declarative()` function.

    **Example**

    ```python
    import edgy
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

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.pkname}={self.pk})"

    async def update(self, **kwargs: Any) -> Any:
        """
        Update operation of the database fields.
        """
        await self.signals.pre_update.send(sender=self.__class__, instance=self)

        kwargs = self._update_auto_now_fields(kwargs, self.fields)
        pk_column = getattr(self.table.c, self.pkname)
        expression = self.table.update().values(**kwargs).where(pk_column == self.pk)
        await self.database.execute(expression)
        await self.signals.post_update.send(sender=self.__class__, instance=self)

        # Update the model instance.
        for key, value in kwargs.items():
            setattr(self, key, value)

        return self

    async def delete(self) -> None:
        """Delete operation from the database"""
        await self.signals.pre_delete.send(sender=self.__class__, instance=self)

        pk_column = getattr(self.table.c, self.pkname)
        expression = self.table.delete().where(pk_column == self.pk)
        await self.database.execute(expression)

        await self.signals.post_delete.send(sender=self.__class__, instance=self)

    async def load(self) -> None:
        # Build the select expression.

        pk_column = getattr(self.table.c, self.pkname)
        expression = self.table.select().where(pk_column == self.pk)

        # Perform the fetch.
        row = await self.database.fetch_one(expression)

        # Update the instance.
        for key, value in dict(row._mapping).items():
            setattr(self, key, value)

    async def _save(self, **kwargs: Any) -> "Model":
        """
        Performs the save instruction.
        """
        expression = self.table.insert().values(**kwargs)
        awaitable = await self.database.execute(expression)
        if not awaitable:
            awaitable = kwargs.get(self.pkname)
        edgy_setattr(self, self.pkname, awaitable)
        return self

    async def save_model_references(self, model_references: Any, model_ref: Any = None) -> None:
        """
        If there is any ModelRef declared in the model, it will generate the subsquent model
        reference records for that same model created.
        """

        for reference in model_references:
            if isinstance(reference, dict):
                model: Type["Model"] = self.meta.model_references[model_ref].__model__  # type: ignore
            else:
                model: Type["Model"] = reference.__model__  # type: ignore

            if isinstance(model, str):
                model = self.meta.registry.models[model]  # type: ignore

            # If the reference did come in a dict format
            # It is necessary to convert into the original ModelRef.
            if isinstance(reference, dict):
                reference = self.meta.model_references[model_ref](**reference)  # type: ignore

            foreign_key_target_field = None
            for name, foreign_key in model.meta.foreign_key_fields.items():
                if foreign_key.target == self.__class__:
                    foreign_key_target_field = name

            if not foreign_key_target_field:
                raise RelationshipNotFound(
                    f"There was no relationship found between '{model.__class__.__name__}' and {self.__class__.__name__}"
                )

            data = reference.model_dump(exclude={"__model__"})
            data[foreign_key_target_field] = self
            await model.query.create(**data)

    def update_model_references(self, **kwargs: Any) -> Any:
        model_refs_set: Set[str] = set()
        model_references: Dict[str, Any] = {}

        for name, value in kwargs.items():
            if name in self.meta.model_references:
                model_references[name] = value
                model_refs_set.add(name)

        for value in model_refs_set:
            kwargs.pop(value)

        return kwargs, model_references

    async def save(
        self,
        force_save: bool = False,
        values: Dict[str, Any] = None,
        **kwargs: Any,
    ) -> Union[Type["Model"], Any]:
        """
        Performs a save of a given model instance.
        When creating a user it will make sure it can update existing or
        create a new one.
        """
        await self.signals.pre_save.send(sender=self.__class__, instance=self)

        extracted_fields = self.extract_db_fields()
        extracted_model_references = self.extract_db_model_references()
        extracted_fields.update(extracted_model_references)

        if getattr(self, "pk", None) is None and self.fields[self.pkname].autoincrement:
            extracted_fields.pop(self.pkname, None)

        self.update_from_dict(dict_values=dict(extracted_fields.items()))

        # Performs the update or the create based on a possible existing primary key
        if getattr(self, "pk", None) is None or force_save:
            validated_values = values or self._extract_values_from_field(
                extracted_values=extracted_fields
            )
            kwargs = self._update_auto_now_fields(values=validated_values, fields=self.fields)
            kwargs, model_references = self.update_model_references(**kwargs)
            await self._save(**kwargs)
        else:
            # Broadcast the initial update details
            # Making sure it only updates the fields that should be updated
            # and excludes the fields aith `auto_now` as true
            validated_values = values or self._extract_values_from_field(
                extracted_values=extracted_fields, is_update=True
            )
            kwargs, model_references = self.update_model_references(**validated_values)
            update_model = {k: v for k, v in validated_values.items() if k in kwargs}

            await self.signals.pre_update.send(
                sender=self.__class__, instance=self, kwargs=update_model
            )
            await self.update(**update_model)

            # Broadcast the update complete
            await self.signals.post_update.send(sender=self.__class__, instance=self)

        # Save the model references
        if model_references:
            for model_ref, references in model_references.items():
                await self.save_model_references(references or [], model_ref=model_ref)

        # Refresh the results
        if any(
            field.server_default is not None
            for name, field in self.fields.items()
            if name not in extracted_fields
        ):
            await self.load()

        await self.signals.post_save.send(sender=self.__class__, instance=self)
        return self

    def __getattr__(self, name: str) -> Any:
        """
        Run an one off query to populate any foreign key making sure
        it runs only once per foreign key avoiding multiple database calls.
        """
        if name not in self.__dict__ and name in self.fields and name != self.pkname:
            run_sync(self.load())
            return self.__dict__[name]
        return super().__getattr__(name)


class ReflectModel(Model, EdgyBaseReflectModel):
    """
    Reflect on async engines is not yet supported, therefore, we need to make a sync_engine
    call.
    """
