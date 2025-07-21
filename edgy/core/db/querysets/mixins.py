from __future__ import annotations

import warnings
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal, cast

import sqlalchemy

from edgy.core.connection.database import Database
from edgy.core.db.context_vars import set_schema, with_schema
from edgy.types import Undefined

if TYPE_CHECKING:
    from edgy import QuerySet


class QuerySetPropsMixin:
    """
    A mixin class providing essential properties for QuerySet objects.

    This class encapsulates properties such as `database`, `table`, `pknames`, and
    `pkcolumns`. These properties are fundamental for QuerySet operations, allowing
    clean access and improved maintainability by isolating them from the main
    QuerySet logic. It also handles the lazy initialization and caching of the
    `_table` and `_database` attributes.
    """

    # Internal SQLAlchemy Table object associated with the queryset.
    _table: sqlalchemy.Table | None = None
    # Internal Database instance associated with the queryset.
    _database: Database | None = None

    @property
    def database(self) -> Database:
        """
        Returns the database instance associated with the queryset.

        If the `_database` attribute is not explicitly set on the queryset, this
        property defaults to retrieving the database configured for the `model_class`
        linked to this queryset. This ensures that every queryset operates within a
        defined database context.

        Returns:
            Database: The database instance that the queryset will use for its
                      operations.
        """
        if self._database is None:
            # Cast to Database is necessary as model_class.database is not directly typed.
            return cast("Database", self.model_class.database)
        return self._database

    @database.setter
    def database(self: QuerySet, value: Database) -> None:
        """
        Sets the database instance for the queryset and clears any cached table
        definitions.

        When a new database instance is assigned, it's crucial to invalidate any
        previously cached table schemas, as the table might need to be re-generated
        or re-associated with the new database context.

        Args:
            value (Database): The new database instance to associate with the queryset.
        """
        self._database = value
        # Clear the cache to ensure table is reloaded based on the new database.
        self._clear_cache()

    @property
    def table(self) -> sqlalchemy.Table:
        """
        Returns the SQLAlchemy Table object associated with the queryset.

        If the `_table` attribute is not explicitly set, this property dynamically
        generates the table schema for the `model_class` using the currently
        `active_schema`. This lazy initialization ensures that the table is only
        built when first accessed and can adapt to schema changes.

        Returns:
            sqlalchemy.Table: The SQLAlchemy Table object that represents the
                              database table for the queryset's model.
        """
        if self._table is None:
            # Cast to sqlalchemy.Table is necessary as table_schema return type is Any.
            return cast("sqlalchemy.Table", self.model_class.table_schema(self.active_schema))
        return self._table

    @table.setter
    def table(self: QuerySet, value: sqlalchemy.Table | None) -> None:
        """
        Sets the SQLAlchemy Table object for the queryset and clears the cache.

        Setting the table directly allows overriding the default table generation.
        Clearing the cache is important to ensure that any cached query components
        that rely on the table definition are re-evaluated.

        Args:
            value (sqlalchemy.Table | None): The SQLAlchemy Table object to set.
                                             Can be None to force regeneration on next access.
        """
        self._table = value
        # Clear the cache to ensure any dependent components are refreshed.
        self._clear_cache()

    @property
    def pknames(self) -> Sequence[str]:
        """
        Returns a sequence of primary key names for the model class associated
        with this queryset.

        This property directly delegates to the `pknames` property of the
        `model_class`, providing a convenient way to access the names of the
        primary key fields.

        Returns:
            Sequence[str]: A sequence (e.g., list or tuple) of strings, where each
                           string is the name of a primary key field.
        """
        # The type ignore is used because model_class.pknames is not explicitly typed
        # as Sequence[str] in some contexts.
        return self.model_class.pknames  # type: ignore

    @property
    def pkcolumns(self) -> Sequence[str]:
        """
        Returns a sequence of primary key column names for the model class
        associated with this queryset.

        This property directly delegates to the `pkcolumns` property of the
        `model_class`, providing access to the underlying database column names
        that constitute the primary key.

        Returns:
            Sequence[str]: A sequence (e.g., list or tuple) of strings, where each
                           string is the name of a primary key column in the
                           database.
        """
        # The type ignore is used because model_class.pkcolumns is not explicitly typed
        # as Sequence[str] in some contexts.
        return self.model_class.pkcolumns  # type: ignore


# A sentinel object used to detect when a keyword-only argument has not been provided.
_sentinel = object()


class TenancyMixin:
    """
    Mixin used for querying a multi-tenant and/or multi-database application.

    This mixin provides methods to switch between different database connections
    and/or database schemas dynamically, allowing a single QuerySet object to
    operate across various tenancy contexts. It facilitates operations in
    environments where data is segregated by tenant or resides in different
    database instances.
    """

    def using(
        self,
        _positional: Any = _sentinel,
        *,
        database: str | Any | None | Database = Undefined,
        schema: str | Any | None | Literal[False] = Undefined,
    ) -> QuerySet:
        """
        Enables and switches the database schema and/or database connection for
        the queryset.

        This method creates a new QuerySet instance that operates within the
        specified database and/or schema context. It's designed to support
        multi-tenancy by allowing dynamic selection of the database or schema
        without modifying the original QuerySet.

        Args:
            _positional (Any): Deprecated positional argument for `schema`. This
                               argument is maintained for backward compatibility but
                               its use is discouraged. It will be treated as the
                               `schema` argument.
            database (str | Database | None): Specifies the database to use.
              - `str`: Name of an extra database connection registered in the model's registry.
              - `Database`: A Database instance to use directly.
              - `None`: Uses the default database from the model's registry.
              - `Undefined` (default): Retains the current database of the queryset.
            schema (str | None | Literal[False]): Specifies the database schema to use.
              - `str`: The schema name to activate.
              - `False`: Unsets the schema, reverting to the active default schema for the model.
              - `None`: Uses no specific schema.
              - `Undefined` (default): Retains the current schema of the queryset.

        Returns:
            QuerySet: A new QuerySet instance configured with the specified database
                      and/or schema settings. This new instance allows chaining
                      operations within the new context.

        Warnings:
            DeprecationWarning: If positional arguments are passed to this method for
                                `_positional`. Users should explicitly use `schema=`
                                keyword argument instead.
        """
        # Check for deprecated positional argument usage.
        if _positional is not _sentinel:
            warnings.warn(
                "Passing positional arguments to using is deprecated. Use schema= instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            schema = _positional
            # If schema was not explicitly set as Undefined (meaning it was passed
            # positionally) and is still Undefined, set it to False to unset the schema.
            if schema is Undefined:
                schema = False

        # Create a clone of the current queryset to avoid modifying the original.
        queryset = cast("QuerySet", self._clone())

        # Process the 'database' argument.
        if database is not Undefined:
            if isinstance(database, Database):
                connection: Database = database
            elif database is None:
                # Use the default database from the model's registry.
                connection = self.model_class.meta.registry.database
            else:
                # Assert that the database name exists in the extra connections.
                assert database is None or database in self.model_class.meta.registry.extra, (
                    f"`{database}` is not in the connections extra of the model"
                    f"`{self.model_class.__name__}` registry"
                )
                # Retrieve the database from extra connections.
                connection = self.model_class.meta.registry.extra[database]
            # Assign the determined connection to the new queryset's database.
            queryset.database = connection

        # Process the 'schema' argument.
        if schema is not Undefined:
            # If schema is False, set using_schema to Undefined to unset it;
            # otherwise, use the provided schema.
            queryset.using_schema = schema if schema is not False else Undefined
            # Get the new schema based on the current queryset's configuration.
            new_schema = queryset.get_schema()
            # If the new schema is different from the active schema, update and
            # invalidate table cache.
            if new_schema != queryset.active_schema:
                queryset.active_schema = new_schema
                queryset.table = None  # Force regeneration of the table with the new schema.

        return queryset

    def using_with_db(
        self, connection_name: str, schema: str | Any | None | Literal[False] = Undefined
    ) -> QuerySet:
        """
        Switches the database connection and optionally the schema for the queryset.

        This method is deprecated in favor of the more flexible `using` method, which
        accepts both `database` and `schema` as keyword arguments.

        Args:
            connection_name (str): The name of the database connection (registered
                                   in the model's registry's `extra` connections)
                                   to switch to.
            schema (str | None | Literal[False]): The schema name to use.
              - `str`: The schema name to activate.
              - `False`: Unsets the schema, reverting to the active default schema.
              - `None`: Uses no specific schema.
              - `Undefined` (default): Retains the current schema.

        Returns:
            QuerySet: A new QuerySet instance configured with the specified database
                      connection and schema.

        Warnings:
            DeprecationWarning: This method is deprecated. Users should migrate to
                                `using(database=..., schema=...)` for future
                                compatibility.
        """
        warnings.warn(
            "'using_with_db' is deprecated in favor of 'using' with schema, database arguments.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Delegate to the `using` method with the appropriate keyword arguments.
        return self.using(database=connection_name, schema=schema)


def activate_schema(tenant_name: str) -> None:
    """
    Activates the specified tenant schema for the current execution context.

    This function sets a context variable that determines the schema used for
    database operations. It is a deprecated function; `with_schema` should be
    used instead for managing schema context more safely and explicitly.

    Args:
        tenant_name (str): The name of the tenant schema to activate.

    Warnings:
        DeprecationWarning: This function is deprecated. Use `with_schema` instead for
                            context-managed schema activation.
    """
    warnings.warn(
        "`activate_schema` is deprecated use `with_schema` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Set the schema in the context variable.
    set_schema(tenant_name)


def deactivate_schema() -> None:
    """
    Deactivates the current tenant schema for the execution context.

    This function unsets the context variable that controls the active schema,
    reverting database operations to use no specific tenant schema (or the
    default schema configured elsewhere). It is a deprecated function;
    `with_schema` should be used instead for managing schema context.

    Warnings:
        DeprecationWarning: This function is deprecated. Use `with_schema` instead for
                            context-managed schema deactivation.
    """
    warnings.warn(
        "`activate_schema` is deprecated use `with_schema` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Set the schema to None in the context variable, effectively deactivating it.
    set_schema(None)


__all__ = [
    "QuerySetPropsMixin",
    "TenancyMixin",
    "with_schema",
    "activate_schema",
    "deactivate_schema",
]
