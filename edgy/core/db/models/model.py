from typing import Any, Dict, Set, Type, Union

from edgy.core.db.models.base import EdgyBaseReflectModel
from edgy.core.db.models.mixins import DeclarativeMixin
from edgy.core.db.models.row import ModelRow
from edgy.core.db.models.utils import pk_from_model_to_clauses, pk_to_dict
from edgy.core.utils.sync import run_sync
from edgy.exceptions import ObjectNotFound, RelationshipNotFound


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

    async def update(self, **kwargs: Any) -> Any:
        """
        Update operation of the database fields.
        """
        await self.signals.pre_update.send_async(self.__class__, instance=self)

        kwargs = self._update_auto_now_fields(kwargs, self.fields)
        expression = self.table.update().values(**kwargs).where(*pk_from_model_to_clauses(self))
        await self.database.execute(expression)
        await self.signals.post_update.send_async(self.__class__, instance=self)

        # Update the model instance.
        for key, value in kwargs.items():
            setattr(self, key, value)

        return self

    async def delete(self) -> None:
        """Delete operation from the database"""
        await self.signals.pre_delete.send_async(self.__class__, instance=self)

        expression = self.table.delete().where(*pk_from_model_to_clauses(self))
        await self.database.execute(expression)

        await self.signals.post_delete.send_async(self.__class__, instance=self)

    async def load(self) -> None:
        # Build the select expression.

        expression = self.table.select().where(*pk_from_model_to_clauses(self))

        # Perform the fetch.
        row = await self.database.fetch_one(expression)
        # check if is in system
        if row is None:
            raise ObjectNotFound("row does not exist anymore")
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
            awaitable = pk_to_dict(self, kwargs)
        for k, v in self.fields["pk"].to_model("pk", awaitable, phase="set").items():
            setattr(self, k, v)
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
            if name in self.meta.model_references:  # type: ignore
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
    ) -> Union["Model", Any]:
        """
        Performs a save of a given model instance.
        When creating a user it will make sure it can update existing or
        create a new one.
        """
        await self.signals.pre_save.send_async(self.__class__, instance=self)

        extracted_fields = self.extract_db_fields()
        extracted_model_references = self.extract_db_model_references()
        extracted_fields.update(extracted_model_references)

        for pkname in self.pknames:
            if getattr(self, pkname, None) is None and self.fields[pkname].autoincrement:
                extracted_fields.pop(pkname, None)

        self.update_from_dict(dict_values=dict(extracted_fields.items()))

        # Performs the update or the create based on a possible existing primary key
        if getattr(self, "pk", None) is None or force_save:
            validated_values = values or self._extract_values_from_field(extracted_values=extracted_fields)
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

            await self.signals.pre_update.send_async(self.__class__, instance=self, kwargs=update_model)
            await self.update(**update_model)

            # Broadcast the update complete
            await self.signals.post_update.send_async(self.__class__, instance=self)

        # Save the model references
        if model_references:
            for model_ref, references in model_references.items():
                await self.save_model_references(references or [], model_ref=model_ref)

        # Refresh the results
        if any(field.server_default is not None for name, field in self.fields.items() if name not in extracted_fields):
            await self.load()

        await self.signals.post_save.send_async(self.__class__, instance=self)
        return self

    def __getattr__(self, name: str) -> Any:
        """
        Run an one off query to populate any foreign key making sure
        it runs only once per foreign key avoiding multiple database calls.
        """
        field = self.meta.fields_mapping.get(name)
        if field is not None and hasattr(field, "__get__"):
            return field.__get__(self)
        if name not in self.__dict__ and field is not None and name not in self.pknames:
            run_sync(self.load())
            return self.__dict__[name]
        return super().__getattr__(name)


class ReflectModel(Model, EdgyBaseReflectModel):
    """
    Reflect on async engines is not yet supported, therefore, we need to make a sync_engine
    call.
    """
