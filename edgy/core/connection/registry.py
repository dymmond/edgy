from functools import cached_property
from typing import Any, Dict, List, Mapping, Union

import sqlalchemy
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.orm import declarative_base as sa_declarative_base

from edgy.core.connection.database import Database, DatabaseURL
from edgy.core.connection.schemas import Schema


class Registry:
    """
    The command center for the models of Edgy.
    """

    db_schema: Union[str, None] = None

    def __init__(self, database: Union[Database, str, DatabaseURL], **kwargs: Any) -> None:
        self.db_schema = kwargs.pop("schema", None)
        extra = kwargs.pop("extra", {})
        self.database: Database = (
            database if isinstance(database, Database) else Database(database, **kwargs)
        )
        self.models: Dict[str, Any] = {}
        self.reflected: Dict[str, Any] = {}
        self.extra: Mapping[str, Database] = {
            k: v if isinstance(v, Database) else Database(v) for k, v in extra.items()
        }
        # when setting a Model or Reflected Model execute the callbacks
        self._callbacks: Dict[str, List[Any]] = {}

        self.schema = Schema(registry=self)
        self.tenant_models: Dict[str, Any] = {}

        self._metadata: sqlalchemy.MetaData = (
            sqlalchemy.MetaData(schema=self.db_schema)
            if self.db_schema is not None
            else sqlalchemy.MetaData()
        )

    @property
    def metadata(self) -> Any:
        for model_class in self.models.values():
            model_class.table_schema(schema=self.db_schema)
        return self._metadata

    @metadata.setter
    def metadata(self, value: sqlalchemy.MetaData) -> None:
        self._metadata = value

    @cached_property
    def declarative_base(self) -> Any:
        if self.db_schema:
            metadata = sqlalchemy.MetaData(schema=self.db_schema)
        else:
            metadata = sqlalchemy.MetaData()
        return sa_declarative_base(metadata=metadata)

    @property
    def engine(self) -> AsyncEngine:
        assert self.database.is_connected and self.database.engine, "database not initialized"
        return self.database.engine

    @property
    def sync_engine(self) -> Engine:
        return self.engine.sync_engine

    def init_models(
        self, *, init_column_mappers: bool = True, init_class_attrs: bool = True
    ) -> None:
        """
        Initializes lazy parts of models meta. Normally not needed to call.
        """
        for model_class in self.models.values():
            model_class.meta.full_init(
                init_column_mappers=init_column_mappers, init_class_attrs=init_class_attrs
            )

        for model_class in self.reflected.values():
            model_class.meta.full_init(
                init_column_mappers=init_column_mappers, init_class_attrs=init_class_attrs
            )

    def invalidate_models(self, *, clear_class_attrs: bool = True) -> None:
        """
        Invalidate all lazy parts of meta. They will automatically re-initialized on access.
        """
        for model_class in self.models.values():
            model_class.meta.invalidate(clear_class_attrs=clear_class_attrs)
        for model_class in self.reflected.values():
            model_class.meta.invalidate(clear_class_attrs=clear_class_attrs)

    async def create_all(self) -> None:
        if self.db_schema:
            await self.schema.create_schema(self.db_schema, True)
        async with self.database as database:
            with database.force_rollback(False):
                await database.create_all(self.metadata)

    async def drop_all(self) -> None:
        if self.db_schema:
            await self.schema.drop_schema(self.db_schema, True, True)
        async with self.database as database:
            with database.force_rollback(False):
                await database.drop_all(self.metadata)
