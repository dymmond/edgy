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
    Properties used by the Queryset are placed in isolation
    for clean access and maintainance.
    """

    _table: sqlalchemy.Table | None = None
    _database: Database | None = None

    @property
    def database(self) -> Database:
        """
        Returns the database instance associated with the queryset.

        If `_database` is not explicitly set, it defaults to the database
        configured for the `model_class`.

        Returns:
            Database: The database instance.
        """
        if self._database is None:
            return cast("Database", self.model_class.database)
        return self._database

    @database.setter
    def database(self: QuerySet, value: Database) -> None:
        """
        Sets the database instance for the queryset and clears the cache.

        Args:
            value (Database): The database instance to set.
        """
        self._database = value
        self._clear_cache()

    @property
    def table(self) -> sqlalchemy.Table:
        """
        Returns the SQLAlchemy Table object associated with the queryset.

        If `_table` is not explicitly set, it generates the table schema
        for the `model_class` based on the `active_schema`.

        Returns:
            sqlalchemy.Table: The SQLAlchemy Table object.
        """
        if self._table is None:
            return cast("sqlalchemy.Table", self.model_class.table_schema(self.active_schema))
        return self._table

    @table.setter
    def table(self: QuerySet, value: sqlalchemy.Table | None) -> None:
        """
        Sets the SQLAlchemy Table object for the queryset and clears the cache.

        Args:
            value (sqlalchemy.Table | None): The SQLAlchemy Table object to set, or None.
        """
        self._table = value
        self._clear_cache()

    @property
    def pknames(self) -> Sequence[str]:
        """
        Returns a sequence of primary key names for the model class.

        Returns:
            Sequence[str]: A sequence of primary key names.
        """
        return self.model_class.pknames  # type: ignore

    @property
    def pkcolumns(self) -> Sequence[str]:
        """
        Returns a sequence of primary key column names for the model class.

        Returns:
            Sequence[str]: A sequence of primary key column names.
        """
        return self.model_class.pkcolumns  # type: ignore


_sentinel = object()


class TenancyMixin:
    """
    Mixin used for querying a possible multi tenancy and multi-database application
    """

    def using(
        self,
        _positional: Any = _sentinel,
        *,
        database: str | Any | None | Database = Undefined,
        schema: str | Any | None | Literal[False] = Undefined,
    ) -> QuerySet:
        """
        Enables and switches the db schema and/or db.

        Generates the registry object pointing to the desired schema
        using the same connection.

        Use schema=False to unset the schema to the active default schema.
        Use database=None to use the default database again.

        Args:
            _positional (Any): Deprecated. Positional argument for schema.
            database (str | Any | None | Database): The name of the database connection
                                                    or a Database instance to use.
                                                    If None, uses the default database.
            schema (str | Any | None | Literal[False]): The schema name to use.
                                                         If False, unsets the schema to
                                                         the active default schema.
                                                         If None, uses no specific schema.

        Returns:
            QuerySet: A new QuerySet instance with the specified database and/or schema.

        Warnings:
            DeprecationWarning: If positional arguments are passed for `_positional`.
        """
        if _positional is not _sentinel:
            warnings.warn(
                "Passing positional arguments to using is deprecated. Use schema= instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            schema = _positional
            if schema is Undefined:
                schema = False

        queryset = cast("QuerySet", self._clone())
        if database is not Undefined:
            if isinstance(database, Database):
                connection: Database = database
            elif database is None:
                connection = self.model_class.meta.registry.database
            else:
                assert database is None or database in self.model_class.meta.registry.extra, (
                    f"`{database}` is not in the connections extra of the model`{self.model_class.__name__}` registry"
                )

                connection = self.model_class.meta.registry.extra[database]
            queryset.database = connection
        if schema is not Undefined:
            queryset.using_schema = schema if schema is not False else Undefined
            new_schema = queryset.get_schema()
            if new_schema != queryset.active_schema:
                queryset.active_schema = new_schema
                queryset.table = None

        return queryset

    def using_with_db(
        self, connection_name: str, schema: str | Any | None | Literal[False] = Undefined
    ) -> QuerySet:
        """
        Switches the database connection and schema

        Args:
            connection_name (str): The name of the database connection to switch to.
            schema (str | Any | None | Literal[False]): The schema name to use.
                                                         If False, unsets the schema to
                                                         the active default schema.
                                                         If None, uses no specific schema.

        Returns:
            QuerySet: A new QuerySet instance with the specified database connection and schema.

        Warnings:
            DeprecationWarning: This method is deprecated in favor of `using` with `database`
                                and `schema` keyword arguments.
        """
        warnings.warn(
            "'using_with_db' is deprecated in favor of 'using' with schema, database arguments.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.using(database=connection_name, schema=schema)


def activate_schema(tenant_name: str) -> None:
    """
    Activates the schema for the context of the query.

    This function sets the schema for the current context, affecting subsequent
    database operations.

    Args:
        tenant_name (str): The name of the tenant schema to activate.

    Warnings:
        DeprecationWarning: This function is deprecated. Use `with_schema` instead.
    """
    warnings.warn(
        "`activate_schema` is deprecated use `with_schema` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    set_schema(tenant_name)


def deactivate_schema() -> None:
    """
    Deactivates the schema for the context of the query.

    This function unsets the current schema, reverting to no specific schema
    for subsequent database operations.

    Warnings:
        DeprecationWarning: This function is deprecated. Use `with_schema` instead.
    """
    warnings.warn(
        "`activate_schema` is deprecated use `with_schema` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    set_schema(None)


__all__ = [
    "QuerySetPropsMixin",
    "TenancyMixin",
    "with_schema",
    "activate_schema",
    "deactivate_schema",
]
