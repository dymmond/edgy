from typing import TYPE_CHECKING, Type, cast

import sqlalchemy
from sqlalchemy.exc import DBAPIError, ProgrammingError

from edgy.core.connection.database import Database
from edgy.exceptions import SchemaError

if TYPE_CHECKING:
    from edgy import Registry


class Schema:
    """
    All the schema operations object.

    All the operations regarding a schema are placed in one object
    """

    def __init__(self, registry: Type["Registry"]) -> None:
        self.registry = registry

    def get_default_schema(self) -> str:
        """
        Returns the default schema which is usually None
        """
        return cast("str", self.registry.engine.dialect.default_schema_name)

    async def activate_schema_path(
        self, database: Database, schema: str, is_shared: bool = True
    ) -> None:
        path = (
            f"SET search_path TO {schema}, shared;"
            if is_shared
            else f"SET search_path TO {schema};"
        )
        expression = sqlalchemy.text(path)
        await database.execute(expression)

    async def create_schema(self, schema: str, if_not_exists: bool = False) -> None:
        """
        Creates a model schema if it does not exist.
        """

        def execute_create(connection: sqlalchemy.Connection) -> None:
            try:
                connection.execute(
                    sqlalchemy.schema.CreateSchema(name=schema, if_not_exists=if_not_exists)  # type: ignore
                )
            except ProgrammingError as e:
                raise SchemaError(detail=e.orig.args[0]) from e  # type: ignore

        # database can be also a TestClient, so use the Database and copy to not have strange error
        async with Database(
            self.registry.database, force_rollback=False
        ) as database, database.transaction():
            await database.run_sync(execute_create)

    async def drop_schema(
        self, schema: str, cascade: bool = False, if_exists: bool = False
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
                raise SchemaError(detail=e.orig.args[0]) from e  # type: ignore

        # database can be also a TestClient, so use the Database and copy to not have strange error
        async with Database(
            self.registry.database, force_rollback=False
        ) as database, database.transaction():
            await database.run_sync(execute_drop)
