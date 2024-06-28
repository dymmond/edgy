from functools import cached_property
from typing import Any, Dict, Mapping, Type

import sqlalchemy
from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.orm import declarative_base as sa_declarative_base

from edgy.conf import settings
from edgy.core.connection.database import Database
from edgy.core.connection.schemas import Schema
from edgy.exceptions import ImproperlyConfigured


class Registry:
    """
    The command center for the models of Edgy.
    """

    def __init__(self, database: Database, **kwargs: Any) -> None:
        self.database: Database = database
        self.models: Dict[str, Any] = {}
        self.reflected: Dict[str, Any] = {}
        self.db_schema = kwargs.get("schema", None)
        self.extra: Mapping[str, Type["Database"]] = kwargs.pop("extra", {})

        self.schema = Schema(registry=self)

        self._metadata: sqlalchemy.MetaData = (
            sqlalchemy.MetaData(schema=self.db_schema) if self.db_schema is not None else sqlalchemy.MetaData()
        )

    @property
    def metadata(self) -> Any:
        for model_class in self.models.values():
            model_class.build(schema=self.db_schema)
        return self._metadata

    @metadata.setter
    def metadata(self, value: sqlalchemy.MetaData) -> None:
        self._metadata = value

    def _get_database_url(self) -> str:
        url = self.database.url
        if not url.driver:
            if url.dialect in settings.postgres_dialects:
                url = url.replace(driver="asyncpg")
            elif url.dialect in settings.mysql_dialects:
                url = url.replace(driver="aiomysql")
            elif url.dialect in settings.sqlite_dialects:
                url = url.replace(driver="aiosqlite")
            elif url.dialect in settings.mssql_dialects:
                raise ImproperlyConfigured("Edgy does not support MSSQL at the moment.")
        elif url.driver in settings.mssql_drivers:
            raise ImproperlyConfigured("Edgy does not support MSSQL at the moment.")
        return str(url)

    @cached_property
    def _get_engine(self) -> AsyncEngine:
        url = self._get_database_url()
        engine = create_async_engine(url)
        return engine

    @cached_property
    def declarative_base(self) -> Any:
        if self.db_schema:
            metadata = sqlalchemy.MetaData(schema=self.db_schema)
        else:
            metadata = sqlalchemy.MetaData()
        return sa_declarative_base(metadata=metadata)

    @property
    def engine(self) -> AsyncEngine:
        return self._get_engine

    @cached_property
    def _get_sync_engine(self) -> Engine:
        url = self._get_database_url()
        engine = create_engine(url)
        return engine

    @property
    def sync_engine(self) -> Engine:
        return self._get_sync_engine

    def init_models(self, *, init_column_mappers: bool=True, init_class_attrs: bool=True) -> None:
        for model_class in self.models.values():
            model_class.meta.full_init(init_column_mappers=init_column_mappers, init_class_attrs=init_class_attrs)

        for model_class in self.reflected.values():
            model_class.meta.full_init(init_column_mappers=init_column_mappers, init_class_attrs=init_class_attrs)

    def invalidate_models(self, *, clear_class_attrs: bool=True) -> None:
        for model_class in self.models.values():
            model_class.meta.invalidate(clear_class_attrs=clear_class_attrs)
        for model_class in self.reflected.values():
            model_class.meta.invalidate(clear_class_attrs=clear_class_attrs)

    async def create_all(self) -> None:
        if self.db_schema:
            await self.schema.create_schema(self.db_schema, True)
        async with self.database:
            async with self.engine.begin() as connection:
                await connection.run_sync(self.metadata.create_all)
        await self.engine.dispose()

    async def drop_all(self) -> None:
        if self.db_schema:
            await self.schema.drop_schema(self.db_schema, True, True)
        async with self.database:
            async with self.engine.begin() as conn:
                await conn.run_sync(self.metadata.drop_all)
                # let's invalidate everything and recalculate. We don't want references.
                self.invalidate_models()
        await self.engine.dispose()
