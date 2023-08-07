from typing import Any, Dict, Type, Union

from edgy.core.db.models.base import EdgyBaseReflectModel
from edgy.core.db.models.mixins import DeclarativeMixin
from edgy.core.db.models.row import ModelRow
from edgy.core.utils.functional import edgy_setattr


class Model(ModelRow, DeclarativeMixin):
    """
    Representation of an Edgy Model.
    This also means it can generate declarative SQLAlchemy models
    from anywhere.
    """

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.pkname}={self.pk})"

    async def update(self, **kwargs: Any) -> Any:
        """
        Update operation of the database fields.
        """
        kwargs = self.update_auto_now_fields(kwargs, self.fields)
        pk_column = getattr(self.table.c, self.pkname)
        expression = self.table.update().values(**kwargs).where(pk_column == self.pk)
        await self.database.execute(expression)

        # Update the model instance.
        for key, value in kwargs.items():
            edgy_setattr(self, key, value)

    async def delete(self) -> None:
        """Delete operation from the database"""
        pk_column = getattr(self.table.c, self.pkname)
        expression = self.table.delete().where(pk_column == self.pk)
        await self.database.execute(expression)

    async def load(self) -> None:
        # Build the select expression.
        pk_column = getattr(self.table.c, self.pkname)
        expression = self.table.select().where(pk_column == self.pk)

        # Perform the fetch.
        row = await self.database.fetch_one(expression)

        # Update the instance.
        for key, value in dict(row._mapping).items():
            edgy_setattr(self, key, value)

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

    async def _update(self, **kwargs: Any) -> Any:
        """
        Performs the save instruction.
        """
        pk_column = getattr(self.table.c, self.pkname)
        expression = self.table.update().values(**kwargs).where(pk_column == self.pk)
        awaitable = await self.database.execute(expression)
        return awaitable

    async def save(
        self: Any, force_save: bool = False, values: Dict[str, Any] = None, **kwargs: Any
    ) -> Union[Type["Model"], Any]:
        """
        Performs a save of a given model instance.
        When creating a user it will make sure it can update existing or
        create a new one.
        """
        extracted_fields = self.extract_db_fields()

        if getattr(self, "pk", None) is None and self.fields[self.pkname].autoincrement:
            extracted_fields.pop(self.pkname, None)

        self.update_from_dict(dict_values=dict(extracted_fields.items()))

        validated_values = values or self.extract_values_from_field(
            extracted_values=extracted_fields
        )
        kwargs = self.update_auto_now_fields(values=validated_values, fields=self.fields)

        # Performs the update or the create based on a possible existing primary key
        if getattr(self, "pk", None) is None or force_save:
            await self._save(**kwargs)
        else:
            await self._update(**kwargs)

        # Refresh the results
        if any(
            field.server_default is not None
            for name, field in self.fields.items()
            if name not in extracted_fields
        ):
            await self.load()
        return self


class ReflectModel(Model, EdgyBaseReflectModel):
    """
    Reflect on async engines is not yet supported, therefore, we need to make a sync_engine
    call.
    """
