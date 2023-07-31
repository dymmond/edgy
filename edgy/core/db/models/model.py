import functools
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Type,
    TypeVar,
    Union,
    cast,
)

import sqlalchemy
from sqlalchemy.engine import Engine

from edgy.core.db.models.mixins import DeclarativeMixin
from edgy.core.db.models.row import ModelRow
from edgy.exceptions import ImproperlyConfigured

M = TypeVar("M", bound="Model")


class Model(ModelRow, DeclarativeMixin):
    """
    Representation of an Edgy Model.
    This also means it can generate declarative SQLAlchemy models
    from anywhere.
    """

    def __repr__(self) -> str:  # pragma nocover
        _repr = {k: getattr(self, k) for k, v in self.meta.fields.items()}
        return f"{self.__class__.__name__}({str(_repr)})"

    async def update(self, **kwargs: Any) -> Any:
        """
        Update operation of the database fields.
        """
        fields = {key: field.validator for key, field in self.fields.items() if key in kwargs}
        validator = Schema(fields=fields)
        kwargs = self._update_auto_now_fields(validator.check(kwargs), self.fields)
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

        fields = {
            key: field.validator for key, field in self.fields.items() if key in extracted_fields
        }
        validator = Schema(fields=fields)
        kwargs = self._update_auto_now_fields(validator.check(extracted_fields), self.fields)

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


class ReflectModel(Model):

    """
    Reflect on async engines is not yet supported, therefore, we need to make a sync_engine
    call.
    """

    @classmethod
    @functools.lru_cache
    def get_engine(cls, url: str) -> Engine:
        return sqlalchemy.create_engine(url)

    @property
    def pk(self) -> Any:
        return getattr(self, self.pkname, None)

    @pk.setter
    def pk(self, value: Any) -> Any:
        setattr(self, self.pkname, value)

    @classmethod
    def build_table(cls) -> Any:
        """
        The inspect is done in an async manner and reflects the objects from the database.
        """
        metadata = cls._meta.registry._metadata  # type: ignore
        tablename = cls._meta.tablename
        return cls.reflect(tablename, metadata)

    @classmethod
    def reflect(cls, tablename, metadata):
        try:
            return sqlalchemy.Table(
                tablename, metadata, autoload_with=cls._meta.registry.sync_engine
            )
        except Exception as e:
            raise ImproperlyConfigured(
                detail=f"Table with the name {tablename} does not exist."
            ) from e
