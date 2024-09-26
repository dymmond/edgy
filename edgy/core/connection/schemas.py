import asyncio
from collections.abc import Sequence
from typing import TYPE_CHECKING, Optional, Union

import sqlalchemy
from sqlalchemy.exc import DBAPIError, ProgrammingError

from edgy.core.connection.database import Database
from edgy.exceptions import SchemaError

if TYPE_CHECKING:
    from edgy import Database, Registry


class Schema:
    """
    All the schema operations object.

    All the operations regarding a schema are placed in one object
    """

    _default_schema: Optional[str]

    def __init__(self, registry: "Registry") -> None:
        self.registry = registry

    @property
    def database(self) -> "Database":
        return self.registry.database

    def get_default_schema(self) -> Optional[str]:
        """
        Returns the default schema which is usually None
        """
        if not hasattr(self, "_default_schema"):
            self._default_schema = self.database.url.sqla_url.get_dialect(True).default_schema_name
        return self._default_schema

    async def activate_schema_path(
        self, database: Database, schema: str, is_shared: bool = True
    ) -> None:
        # INSECURE, but not used
        path = (
            f"SET search_path TO {schema}, shared;"
            if is_shared
            else f"SET search_path TO {schema};"
        )
        expression = sqlalchemy.text(path)
        await database.execute(expression)

    async def create_schema(
        self,
        schema: str,
        if_not_exists: bool = False,
        init_models: bool = False,
        init_tenant_models: bool = False,
        update_cache: bool = True,
        databases: Sequence[Union[str, None]] = (None,),
    ) -> None:
        """
        Creates a model schema if it does not exist.
        """
        tables: list[sqlalchemy.Table] = []
        if init_models:
            for model_class in self.registry.models.values():
                model_class.table_schema(schema=schema, update_cache=update_cache)
        if init_tenant_models and init_models:
            for model_class in self.registry.tenant_models.values():
                model_class.table_schema(schema=schema, update_cache=update_cache)
        elif init_tenant_models:
            for model_class in self.registry.tenant_models.values():
                tables.append(model_class.table_schema(schema=schema, update_cache=update_cache))

        def execute_create(connection: sqlalchemy.Connection) -> None:
            try:
                connection.execute(
                    sqlalchemy.schema.CreateSchema(name=schema, if_not_exists=if_not_exists)  # type: ignore
                )
            except ProgrammingError as e:
                raise SchemaError(detail=e.orig.args[0]) from e
            for table in tables:
                table.create(connection, checkfirst=if_not_exists)
            if init_models:
                self.registry.metadata.create_all(connection, checkfirst=if_not_exists)

        ops = []
        for database in databases:
            db = self.registry.database if database is None else self.registry.extra[database]
            # don't warn here about inperformance
            async with db as db:
                with db.force_rollback(False):
                    ops.append(db.run_sync(execute_create))
        await asyncio.gather(*ops)

    async def drop_schema(
        self,
        schema: str,
        cascade: bool = False,
        if_exists: bool = False,
        databases: Sequence[Union[str, None]] = (None,),
    ) -> None:
        """
        Drops an existing model schema.
        """

        def execute_drop(connection: sqlalchemy.Connection) -> None:
            try:
                connection.execute(
                    sqlalchemy.schema.DropSchema(name=schema, cascade=cascade, if_exists=if_exists)  # type: ignore
                )
            except DBAPIError as e:
                raise SchemaError(detail=e.orig.args[0]) from e

        ops = []

        for database in databases:
            db = self.registry.database if database is None else self.registry.extra[database]
            # don't warn here about inperformance
            async with db as db:
                with db.force_rollback(False):
                    ops.append(db.run_sync(execute_drop))
        await asyncio.gather(*ops)
