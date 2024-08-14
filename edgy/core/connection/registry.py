from functools import cached_property
from typing import Any, Dict, Mapping, Union

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

    def __init__(self, database: Union[Database, str, DatabaseURL], **kwargs: Any) -> None:
        self.database: Database = (
            database if isinstance(database, Database) else Database(database)
        )
        self.models: Dict[str, Any] = {}
        self.reflected: Dict[str, Any] = {}
        self.db_schema = kwargs.get("schema", None)
        self.extra: Mapping[str, Database] = {
            k: v if isinstance(v, Database) else Database(v)
            for k, v in kwargs.pop("extra", {}).items()
        }

        self.schema = Schema(registry=self)

        self._metadata: sqlalchemy.MetaData = (
            sqlalchemy.MetaData(schema=self.db_schema)
            if self.db_schema is not None
            else sqlalchemy.MetaData()
        )

    @property
    def metadata(self) -> Any:
        for model_class in self.models.values():
            model_class.build(schema=self.db_schema)
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
        assert self.database.engine, "database not initialized"
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
        # database can be also a TestClient, so use the Database and copy to not have strange error
        async with Database(
            self.database, force_rollback=False
        ) as database, database.transaction():
            await database.create_all(self.metadata)

    async def drop_all(self) -> None:
        if self.db_schema:
            await self.schema.drop_schema(self.db_schema, True, True)
        # database can be also a TestClient, so use the Database and copy to not have strange error
        async with Database(
            self.database, force_rollback=False
        ) as database, database.transaction():
            await database.drop_all(self.metadata)
