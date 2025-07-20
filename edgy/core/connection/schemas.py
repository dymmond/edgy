import asyncio
import warnings
from collections.abc import Sequence
from typing import TYPE_CHECKING

import sqlalchemy
from sqlalchemy.exc import DBAPIError, ProgrammingError

from edgy.core.connection.database import Database
from edgy.core.db.context_vars import NO_GLOBAL_FIELD_CONSTRAINTS
from edgy.exceptions import SchemaError

if TYPE_CHECKING:
    from edgy import Registry


class Schema:
    """
    Manages all schema-related operations within the Edgy framework.

    This class encapsulates functionalities for creating, dropping, and
    introspecting database schemas, ensuring proper model integration
    within multi-tenant or schema-isolated environments.
    """

    _default_schema: str | None

    def __init__(self, registry: "Registry") -> None:
        """
        Initializes the Schema manager with a given registry.

        Args:
            registry: The Edgy registry instance, providing access to
                      models, databases, and other core components.
        """
        self.registry = registry

    @property
    def database(self) -> "Database":
        """
        Provides direct access to the default database configured in the registry.

        Returns:
            The default database instance from the registry.
        """
        return self.registry.database

    def get_default_schema(self) -> str | None:
        """
        Retrieves the default schema name from the underlying database dialect.

        This method caches the default schema name after its first retrieval
        to optimize subsequent calls.

        Returns:
            The name of the default schema, or None if not applicable or found.
        """
        # Check if the _default_schema attribute has already been set.
        if not hasattr(self, "_default_schema"):
            # If not set, retrieve the default schema name from the database URL's
            # SQLAlchemy dialect and store it.
            self._default_schema = self.database.url.sqla_url.get_dialect(True).default_schema_name
        # Return the cached default schema name.
        return self._default_schema

    async def activate_schema_path(
        self, database: Database, schema: str, is_shared: bool = True
    ) -> None:
        """
        Activates a specific schema within the database connection's search path.

        This method modifies the `search_path` for the current database session,
        allowing queries to implicitly reference objects within the specified schema.

        Warning: This method is deprecated and considered insecure due to improper
        schema escaping. It should not be used in production environments.

        Args:
            database: The database instance on which to activate the schema path.
            schema: The name of the schema to add to the search path.
            is_shared: If True, adds 'shared' to the search path along with the
                       specified schema. Defaults to True.
        """
        # Issue a deprecation warning as this method is insecure.
        warnings.warn(
            "`activate_schema_path` is dangerous because the schema is not properly "
            "escaped and deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Construct the SQL command to set the search_path.
        # If is_shared is True, include 'shared' in the path.
        path = (
            f"SET search_path TO {schema}, shared;"
            if is_shared
            else f"SET search_path TO {schema};"
        )
        # Convert the SQL string into a SQLAlchemy text expression.
        expression = sqlalchemy.text(path)
        # Execute the SQL expression on the provided database.
        await database.execute(expression)

    async def create_schema(
        self,
        schema: str,
        if_not_exists: bool = False,
        init_models: bool = False,
        init_tenant_models: bool = False,
        update_cache: bool = True,
        databases: Sequence[str | None] = (None,),
    ) -> None:
        """
        Creates a new database schema and optionally initializes models within it.

        This method handles the creation of a new schema and can populate it
        with tables for both regular models and tenant-specific models,
        respecting global field constraints.

        Args:
            schema: The name of the schema to be created.
            if_not_exists: If True, the schema will only be created if it does
                           not already exist, preventing an error. Defaults to False.
            init_models: If True, all models registered with the registry will have
                         their tables created within the new schema. Defaults to False.
            init_tenant_models: If True, tenant-specific models will have their
                               tables created within the new schema. This operation
                               temporarily bypasses global field constraints. Defaults to False.
            update_cache: If True, the model's schema cache will be updated.
                          Defaults to True.
            databases: A sequence of database names (keys from `registry.extra`)
                       or None for the default database, on which the schema
                       should be created. Defaults to `(None,)`, meaning only
                       the default database.
        Raises:
            SchemaError: If there is an issue during schema creation or table
                         initialization within the schema.
        """
        tenant_tables: list[sqlalchemy.Table] = []
        # If init_models is True, iterate through all registered models and
        # update their table schema and cache.
        if init_models:
            for model_class in self.registry.models.values():
                model_class.table_schema(schema=schema, update_cache=update_cache)

        # If init_tenant_models is True, handle the creation of tenant-specific model tables.
        if init_tenant_models:
            # Temporarily disable global field constraints for tenant model building.
            token = NO_GLOBAL_FIELD_CONSTRAINTS.set(True)
            try:
                # Iterate through tenant models and build their tables with the specified schema.
                for model_class in self.registry.tenant_models.values():
                    tenant_tables.append(model_class.build(schema=schema))
            finally:
                # Ensure global field constraints are re-enabled after processing tenant models.
                NO_GLOBAL_FIELD_CONSTRAINTS.reset(token)

            # Perform a second pass to add global field constraints to tenant models.
            for model_class in self.registry.tenant_models.values():
                model_class.add_global_field_constraints(schema=schema)

        def execute_create(connection: sqlalchemy.Connection, name: str | None) -> None:
            """
            Internal helper function to execute the schema and table creation
            within a given database connection.
            """
            try:
                # Attempt to create the schema.
                connection.execute(
                    sqlalchemy.schema.CreateSchema(name=schema, if_not_exists=if_not_exists)
                )
            except ProgrammingError as e:
                # Raise a SchemaError if there's a programming error during schema creation.
                raise SchemaError(detail=e.orig.args[0]) from e

            # If tenant_tables exist, create them within the schema.
            if tenant_tables:
                self.registry.metadata_by_name[name].create_all(
                    connection, checkfirst=if_not_exists, tables=tenant_tables
                )
            # If init_models is True, create all registered model tables within the schema.
            if init_models:
                self.registry.metadata_by_name[name].create_all(
                    connection, checkfirst=if_not_exists
                )

        ops = []
        # Iterate through the specified databases to perform schema creation.
        for database_name in databases:
            # Determine which database instance to use based on database_name.
            db = (
                self.registry.database
                if database_name is None
                else self.registry.extra[database_name]
            )
            # Enter an asynchronous context for the database connection, disabling rollback.
            # prevents warning of inperformance
            async with db as db:
                with db.force_rollback(False):
                    # Append the run_sync operation to the list of operations.
                    ops.append(db.run_sync(execute_create, database_name))
        # Await all schema creation operations concurrently.
        await asyncio.gather(*ops)

    async def drop_schema(
        self,
        schema: str,
        cascade: bool = False,
        if_exists: bool = False,
        databases: Sequence[str | None] = (None,),
    ) -> None:
        """
        Drops an existing database schema, optionally cascading the drop
        to all contained objects.

        Args:
            schema: The name of the schema to be dropped.
            cascade: If True, all objects (tables, views, etc.) within the
                     schema will also be dropped. Defaults to False.
            if_exists: If True, the schema will only be dropped if it exists,
                       preventing an error if it does not. Defaults to False.
            databases: A sequence of database names (keys from `registry.extra`)
                       or None for the default database, from which the schema
                       should be dropped. Defaults to `(None,)`, meaning only
                       the default database.
        Raises:
            SchemaError: If there is an issue during schema drop operation.
        """

        def execute_drop(connection: sqlalchemy.Connection) -> None:
            """
            Internal helper function to execute the schema drop
            within a given database connection.
            """
            try:
                # Attempt to drop the schema.
                connection.execute(
                    sqlalchemy.schema.DropSchema(name=schema, cascade=cascade, if_exists=if_exists)
                )
            except DBAPIError as e:
                # Raise a SchemaError if there's a database API error during schema drop.
                raise SchemaError(detail=e.orig.args[0]) from e

        ops = []
        # Iterate through the specified databases to perform schema drop.
        for database_name in databases:
            # Determine which database instance to use based on database_name.
            db = (
                self.registry.database
                if database_name is None
                else self.registry.extra[database_name]
            )
            # Enter an asynchronous context for the database connection, disabling rollback.
            # prevents warning of inperformance
            async with db as db:
                with db.force_rollback(False):
                    # Append the run_sync operation to the list of operations.
                    ops.append(db.run_sync(execute_drop))
        # Await all schema drop operations concurrently.
        await asyncio.gather(*ops)

    async def get_metadata_of_all_schemes(
        self, database: Database, *, no_reflect: bool = False
    ) -> tuple[sqlalchemy.MetaData, list[str]]:
        """
        Retrieves metadata and a list of all schema names for a given database.

        This method reflects the table structures for registered models
        within each discovered schema if `no_reflect` is False.

        Args:
            database: The database instance from which to retrieve schema metadata.
            no_reflect: If True, tables will not be reflected into the metadata.
                        Defaults to False.

        Returns:
            A tuple containing:
                - sqlalchemy.MetaData: An SQLAlchemy MetaData object populated
                                       with reflected tables (if `no_reflect` is False).
                - list[str]: A list of schema names found in the database.
        """
        # Get a set of all table names registered in the registry.
        tablenames = self.registry.get_tablenames()

        async with database as database:
            # Initialize an empty list to store schema names.
            list_schemes: list[str] = []
            # Create a new SQLAlchemy MetaData object.
            metadata = sqlalchemy.MetaData()
            # Force no rollback for the database connection.
            with database.force_rollback(False):

                def wrapper(connection: sqlalchemy.Connection) -> None:
                    """
                    Internal wrapper function to perform synchronous database
                    inspection and reflection.
                    """
                    nonlocal list_schemes
                    # Create an inspector from the database connection.
                    inspector = sqlalchemy.inspect(connection)
                    # Get the default schema name from the inspector.
                    default_schema_name = inspector.default_schema_name
                    # Get all schema names and replace the default schema name with an empty string.
                    list_schemes = [
                        "" if default_schema_name == schema else schema
                        for schema in inspector.get_schema_names()
                    ]
                    # If no_reflect is False, reflect table metadata for each schema.
                    if not no_reflect:
                        for schema in list_schemes:
                            metadata.reflect(
                                connection, schema=schema, only=lambda name, _: name in tablenames
                            )

                # Run the synchronous wrapper function on the database.
                await database.run_sync(wrapper)
                # Return the populated metadata and the list of schema names.
                return metadata, list_schemes

    async def get_schemes_tree(
        self, *, no_reflect: bool = False
    ) -> dict[str | None, tuple[str, sqlalchemy.MetaData, list[str]]]:
        """
        Builds a comprehensive tree-like structure of schemas across all
        registered databases.

        Each entry in the resulting dictionary represents a database (identified
        by its name or None for the default), containing its URL, its SQLAlchemy
        MetaData, and a list of schema names.

        Args:
            no_reflect: If True, tables will not be reflected into the metadata
                        for any schema. Defaults to False.

        Returns:
            A dictionary where keys are database names (or None for the default
            database) and values are tuples containing:
                - str: The URL of the database.
                - sqlalchemy.MetaData: The MetaData object for the database.
                - list[str]: A list of schema names found in that database.
        """
        # Initialize the schemes_tree dictionary.
        schemes_tree: dict[str | None, tuple[str, sqlalchemy.MetaData, list[str]]] = {
            None: (
                str(self.database.url),
                # Get metadata and schemes for the default database.
                *(
                    await self.get_metadata_of_all_schemes(
                        self.registry.database, no_reflect=no_reflect
                    )
                ),
            )
        }
        # Iterate through extra databases registered in the registry.
        for key, val in self.registry.extra.items():
            # Populate schemes_tree for each extra database.
            schemes_tree[key] = (
                str(val.url),
                # Get metadata and schemes for the current extra database.
                *(await self.get_metadata_of_all_schemes(val, no_reflect=no_reflect)),
            )
        # Return the complete schemes_tree.
        return schemes_tree


__all__ = ["Schema"]
