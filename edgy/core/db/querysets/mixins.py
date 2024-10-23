import warnings
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal, Optional, Union, cast

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

    _table: Optional["sqlalchemy.Table"] = None
    _database: Optional["Database"] = None

    @property
    def database(self) -> Database:
        if self._database is None:
            return cast("Database", self.model_class.database)
        return self._database

    @database.setter
    def database(self, value: Database) -> None:
        self._database = value

    @property
    def table(self) -> sqlalchemy.Table:
        if self._table is None:
            return cast("sqlalchemy.Table", self.model_class.table_schema(self.active_schema))
        return self._table

    @table.setter
    def table(self, value: Optional[sqlalchemy.Table]) -> None:
        self._table = value

    @property
    def pknames(self) -> Sequence[str]:
        return self.model_class.pknames  # type: ignore

    @property
    def pkcolumns(self) -> Sequence[str]:
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
        database: Union[str, Any, None, "Database"] = Undefined,
        schema: Union[str, Any, None, Literal[False]] = Undefined,
    ) -> "QuerySet":
        """
        Enables and switches the db schema and/or db.

        Generates the registry object pointing to the desired schema
        using the same connection.

        Use schema=False to unset the schema to the active default schema.
        Use database=None to use the default database again.
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
                assert (
                    database is None or database in self.model_class.meta.registry.extra
                ), f"`{database}` is not in the connections extra of the model`{self.model_class.__name__}` registry"

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
        self, connection_name: str, schema: Union[str, Any, None, Literal[False]] = Undefined
    ) -> "QuerySet":
        """
        Switches the database connection and schema
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
