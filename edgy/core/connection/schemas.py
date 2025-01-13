import asyncio
import warnings
from collections.abc import Sequence
from typing import TYPE_CHECKING, Optional, Union

import sqlalchemy
from sqlalchemy.exc import DBAPIError, ProgrammingError

from edgy.core.connection.database import Database
from edgy.core.db.context_vars import NO_GLOBAL_FIELD_CONSTRAINTS
from edgy.exceptions import SchemaError

if TYPE_CHECKING:
    from edgy import Registry


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
        # INSECURE, but not used by default. Add warning
        # TODO: remove when there are no users of the method
        warnings.warn(
            "`activate_schema_path` is dangerous because the schema is not properly escaped and deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
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
        tenant_tables: list[sqlalchemy.Table] = []
        if init_models:
            for model_class in self.registry.models.values():
                model_class.table_schema(schema=schema, update_cache=update_cache)
        if init_tenant_models:
            token = NO_GLOBAL_FIELD_CONSTRAINTS.set(True)
            try:
                for model_class in self.registry.tenant_models.values():
                    tenant_tables.append(model_class.build(schema=schema))
            finally:
                NO_GLOBAL_FIELD_CONSTRAINTS.reset(token)
            # we need two passes
            for model_class in self.registry.tenant_models.values():
                model_class.add_global_field_constraints(schema=schema)

        def execute_create(connection: sqlalchemy.Connection, name: Optional[str]) -> None:
            try:
                connection.execute(
                    sqlalchemy.schema.CreateSchema(name=schema, if_not_exists=if_not_exists)
                )
            except ProgrammingError as e:
                raise SchemaError(detail=e.orig.args[0]) from e
            if tenant_tables:
                self.registry.metadata_by_name[name].create_all(
                    connection, checkfirst=if_not_exists, tables=tenant_tables
                )
            if init_models:
                self.registry.metadata_by_name[name].create_all(
                    connection, checkfirst=if_not_exists
                )

        ops = []
        for database_name in databases:
            db = (
                self.registry.database
                if database_name is None
                else self.registry.extra[database_name]
            )
            # don't warn here about inperformance
            async with db as db:
                with db.force_rollback(False):
                    ops.append(db.run_sync(execute_create, database_name))
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
                    sqlalchemy.schema.DropSchema(name=schema, cascade=cascade, if_exists=if_exists)
                )
            except DBAPIError as e:
                raise SchemaError(detail=e.orig.args[0]) from e

        ops = []

        for database_name in databases:
            db = (
                self.registry.database
                if database_name is None
                else self.registry.extra[database_name]
            )
            # don't warn here about inperformance
            async with db as db:
                with db.force_rollback(False):
                    ops.append(db.run_sync(execute_drop))
        await asyncio.gather(*ops)

    async def get_metadata_of_all_schemes(
        self, database: Database, *, no_reflect: bool = False
    ) -> tuple[sqlalchemy.MetaData, list[str]]:
        tablenames = self.registry.get_tablenames()

        async with database as database:
            list_schemes: list[str] = []
            metadata = sqlalchemy.MetaData()

            def wrapper(connection: sqlalchemy.Connection) -> None:
                nonlocal list_schemes
                inspector = sqlalchemy.inspect(connection)
                default_schema_name = inspector.default_schema_name
                list_schemes = [
                    "" if default_schema_name == schema else schema
                    for schema in inspector.get_schema_names()
                ]
                if not no_reflect:
                    for schema in list_schemes:
                        metadata.reflect(
                            connection, schema=schema, only=lambda name, _: name in tablenames
                        )

            await database.run_sync(wrapper)
            return metadata, list_schemes

    async def get_schemes_tree(
        self, *, no_reflect: bool = False
    ) -> dict[Union[str, None], tuple[str, sqlalchemy.MetaData, list[str]]]:
        schemes_tree: dict[Union[str, None], tuple[str, sqlalchemy.MetaData, list[str]]] = {
            None: (
                str(self.database.url),
                *(
                    await self.get_metadata_of_all_schemes(
                        self.registry.database, no_reflect=no_reflect
                    )
                ),
            )
        }
        for key, val in self.registry.extra.items():
            schemes_tree[key] = (
                str(val.url),
                *(await self.get_metadata_of_all_schemes(val, no_reflect=no_reflect)),
            )
        return schemes_tree


__all__ = ["Schema"]
