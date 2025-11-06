from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

import sqlalchemy

from edgy.core.connection.database import Database

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
