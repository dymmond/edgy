import asyncio
import copy
from typing import TYPE_CHECKING, Any, Callable, cast

import sqlalchemy

from edgy.core.connection.database import Database
from edgy.core.connection.registry import Registry

if TYPE_CHECKING:
    from edgy import QuerySet


class QuerySetPropsMixin:
    """
    Properties used by the Queryset are placed in isolation
    for clean access and maintainance.
    """

    @property
    def database(self) -> Any:
        if not self._db:
            return self.model_class.meta.registry.database  # type: ignore
        return self._db.database

    @property
    def table(self) -> sqlalchemy.Table:
        if not self._db:
            return self.model_class.table  # type: ignore
        table = copy.copy(self.model_class.table)
        table.schema = self._db._schema
        return cast("sqlalchemy.Table", table)

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
        queryset: "QuerySet" = self.clone()
        registry = Registry(database=self.database, schema=schema)
        queryset._db = registry
        return queryset

    def using_with_db(self, database: Database, schema: str) -> "QuerySet":
        """
        Enables and switches the db schema and the database connection.

        Generates the registry object pointing to the desired schema
        using a different database connection.
        """
        queryset: "QuerySet" = self.clone()
        registry = Registry(database=database, schema=schema)
        queryset._db = registry
        return queryset
