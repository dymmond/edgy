import asyncio
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

import sqlalchemy

from edgy.core.connection.database import Database
from edgy.core.db.context_vars import set_queryset_database, set_queryset_schema

if TYPE_CHECKING:
    from edgy import QuerySet


class QuerySetPropsMixin:
    """
    Properties used by the Queryset are placed in isolation
    for clean access and maintainance.
    """

    @property
    def database(self) -> Database:
        if getattr(self, "_database", None) is None:
            return cast("Database", self.model_class.meta.registry.database)
        return self._database

    @database.setter
    def database(self, value: Database) -> None:
        self._database = value

    @property
    def table(self) -> sqlalchemy.Table:
        if getattr(self, "_table", None) is None:
            return cast("sqlalchemy.Table", self.model_class.table)
        return self._table

    @table.setter
    def table(self, value: sqlalchemy.Table) -> None:
        self._table = value

    @property
    def pkname(self) -> Any:
        return self.model_class.pkname  # type: ignore

    @property
    def is_m2m(self) -> bool:
        return bool(self.model_class.meta.is_multi)

    @property
    def m2m_related(self) -> str:
        return self._m2m_related

    @m2m_related.setter
    def m2m_related(self, value: str) -> None:
        self._m2m_related = value


class TenancyMixin:
    """
    Mixin used for querying a possible multi tenancy application
    """

    def run_async(self, fn: Callable[..., Any]) -> asyncio.BaseEventLoop:
        """
        Returns the event loop from the corresponding policy.
        """
        return asyncio.get_event_loop().run_until_complete(fn)

    def using(self, schema: str) -> "QuerySet":
        """
        Enables and switches the db schema.

        Generates the registry object pointing to the desired schema
        using the same connection.
        """
        queryset = set_queryset_schema(self, self.model_class, value=schema)
        return queryset

    def using_with_db(self, database: Database, schema: Optional[str] = None) -> "QuerySet":
        """
        Enables and switches the db schema and the database connection.

        Generates the registry object pointing to the desired schema
        using a different database connection.
        """
        if schema:
            return set_queryset_database(self, self.model_class, database, schema)
        return set_queryset_database(self, self.model_class, database)
