import asyncio
from typing import TYPE_CHECKING, Any, Callable, cast

import sqlalchemy

from edgy.core.connection.database import Database
from edgy.core.db.context_vars import CONTEXT_SCHEMA, get_context_db_schema

if TYPE_CHECKING:
    from edgy import QuerySet


class QuerySetPropsMixin:
    """
    Properties used by the Queryset are placed in isolation
    for clean access and maintainance.
    """

    @property
    def database(self) -> Database:
        if not self._database:
            return cast("Database", self.model_class.meta.registry.database)
        return self._database

    @database.setter
    def database(self, value: Database) -> None:
        self._database = value

    @property
    def schema(self) -> str:
        return get_context_db_schema()

    @property
    def table(self) -> sqlalchemy.Table:
        return cast("sqlalchemy.Table", self.model_class.table)

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

        CONTEXT_SCHEMA.set(schema)
        return cast("QuerySet", self)

    def using_with_db(self, database: Database, schema: str) -> "QuerySet":
        """
        Enables and switches the db schema and the database connection.

        Generates the registry object pointing to the desired schema
        using a different database connection.
        """
        queryset: "QuerySet" = self.clone()
        queryset.database = database
        CONTEXT_SCHEMA.set(schema)
        return queryset
