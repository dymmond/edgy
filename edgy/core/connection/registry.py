from functools import cached_property
from typing import Any

import sqlalchemy
from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.orm import declarative_base as sa_declarative_base

from edgy.conf import settings
from edgy.core.connection.database import Database
from edgy.exceptions import ImproperlyConfigured


class Registry:
    """
    The command center for the models being generated
    for Edgy.
    """

    def __init__(self, database: Database, **kwargs: Any) -> None:
        assert isinstance(
            database, Database
        ), "database must be an instance of edgy.core.connection.Database"

        self.database = database
        self.models: Any = {}
        self.reflected: Any = {}
        self._schema = kwargs.get("schema", None)

        if self._schema:
            self._metadata = sqlalchemy.MetaData(schema=self._schema)
        else:
            self._metadata = sqlalchemy.MetaData()

    @property
    def metadata(self) -> Any:
        for model_class in self.models.values():
            model_class.build()
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
        if self._schema:
            metadata = sqlalchemy.MetaData(schema=self._schema)
        else:
            metadata = sqlalchemy.MetaData()
        return sa_declarative_base(metadata=metadata)

    @property
    def engine(self):  # type: ignore
        return self._get_engine

    @cached_property
    def _get_sync_engine(self) -> Engine:
        url = self._get_database_url()
        engine = create_engine(url)
        return engine

    @property
    def sync_engine(self):  # type: ignore
        return self._get_sync_engine

    async def create_all(self) -> None:
        async with self.database:
            async with self.engine.begin() as connection:
                await connection.run_sync(self.metadata.create_all)

        await self.engine.dispose()

    async def drop_all(self) -> None:
        async with self.database:
            async with self.engine.begin() as conn:
                await conn.run_sync(self.metadata.drop_all)
        await self.engine.dispose()
