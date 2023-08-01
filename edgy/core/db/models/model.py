from typing import Any, TypeVar

import edgy
from edgy.core.db.models.base import EdgyBaseReflectModel
from edgy.core.db.models.mixins import DeclarativeMixin
from edgy.core.db.models.row import ModelRow

M = TypeVar("M", bound="Model")


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
        kwargs = self._update_auto_now_fields(kwargs, self.fields)
        pk_column = getattr(self.table.c, self.pkname)
        expression = self.table.update().values(**kwargs).where(pk_column == self.pk)
        await self.database.execute(expression)

        # Update the model instance.
        for key, value in kwargs.items():
            setattr(self, key, value)

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
            setattr(self, key, value)

    async def save(self: M) -> M:
        """
        Performs a save of a given model instance.
        When creating a user it will make sure it can update existing or
        create a new one.
        """
        extracted_fields = self.extract_db_fields()

        if getattr(self, "pk", None) is None and self.fields[self.pkname].autoincrement:
            extracted_fields.pop(self.pkname, None)

        self.update_from_dict(dict(extracted_fields.items()))

        validated_values = self.extract_values_from_field(extracted_fields)
        kwargs = self._update_auto_now_fields(validated_values, self.fields)

        # Performs the update or the create based on a possible existing primary key
        if getattr(self, "pk", None) is None:
            expression = self.table.insert().values(**kwargs)
            pk_column = await self.database.execute(expression)
            setattr(self, self.pkname, pk_column)
        else:
            pk_column = getattr(self.table.c, self.pkname)
            expression = self.table.update().values(**kwargs).where(pk_column == self.pk)
            await self.database.execute(expression)

        # Refresh the results
        if any(
            field.server_default is not None
            for name, field in self.fields.items()
            if name not in extracted_fields
        ):
            await self.load()
        return self


class ReflectModel(EdgyBaseReflectModel):
    """
    Reflect on async engines is not yet supported, therefore, we need to make a sync_engine
    call.
    """
