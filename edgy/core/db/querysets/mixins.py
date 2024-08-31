from typing import TYPE_CHECKING, Any, Optional, Sequence, Union, cast

import sqlalchemy

from edgy.core.connection.database import Database
from edgy.core.db.context_vars import set_schema
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
            return cast("Database", self.model_class.meta.registry.database)
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


class TenancyMixin:
    """
    Mixin used for querying a possible multi tenancy application
    """

    def using(self, schema: Union[str, Any, None] = Undefined) -> "QuerySet":
        """
        Enables and switches the db schema.

        Generates the registry object pointing to the desired schema
        using the same connection.
        """
        queryset = cast("QuerySet", self._clone())
        queryset.using_schema = schema
        queryset.active_schema = queryset.get_schema()
        queryset.table = None  # type: ignore
        return queryset

    def using_with_db(
        self, connection_name: str, schema: Union[str, Any] = Undefined
    ) -> "QuerySet":
        """
        Enables and switches the database connection.

        Generates the new queryset using the selected connection provided in the extra of the model
        registry.
        """
        assert (
            connection_name in self.model_class.meta.registry.extra
        ), f"`{connection_name}` is not in the connections extra of the model`{self.model_class.__name__}` registry"

        connection: Database = self.model_class.meta.registry.extra[connection_name]
        queryset = cast("QuerySet", self._clone())
        queryset.database = connection
        queryset.using_schema = schema
        queryset.active_schema = queryset.get_schema()
        queryset.table = None  # type: ignore
        return queryset


def activate_schema(tenant_name: str) -> None:
    """
    Activates the tenant for the context of the query.
    """
    set_schema(tenant_name)


def deactivate_schema() -> None:
    """
    Deactivates the tenant for the context of the query.
    """
    set_schema(None)
