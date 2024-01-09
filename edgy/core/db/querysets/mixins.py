from typing import TYPE_CHECKING, Any, Optional, Type, TypeVar, Union, cast

import sqlalchemy

from edgy.core.connection.database import Database
from edgy.core.db.context_vars import set_queryset_database, set_queryset_schema, set_schema

if TYPE_CHECKING:
    from edgy import QuerySet, Registry
    from edgy.core.db.models import Model, ReflectModel


_EdgyModel = TypeVar("_EdgyModel", bound="Model")
ReflectEdgyModel = TypeVar("ReflectEdgyModel", bound="ReflectModel")

EdgyModel = Union[_EdgyModel, ReflectEdgyModel]


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

    def using(self, schema: str) -> "QuerySet":
        """
        Enables and switches the db schema.

        Generates the registry object pointing to the desired schema
        using the same connection.
        """
        queryset = set_queryset_schema(self, self.model_class, value=schema)
        return queryset

    def using_with_db(self, connection_name: str, schema: Optional[str] = None) -> "QuerySet":
        """
        Enables and switches the database connection.

        Generates the new queryset using the selected connection provided in the extra of the model
        registry.
        """
        assert (
            connection_name in self.model_class.meta.registry.extra
        ), f"`{connection_name}` is not in the connections extra of the model`{self.model_class.__name__}` registry"

        connection: Type["Registry"] = self.model_class.meta.registry.extra[connection_name]
        if schema:
            return set_queryset_database(self, self.model_class, connection, schema)
        queryset = set_queryset_database(self, self.model_class, connection)
        return queryset


def activate_schema(tenant_name: str) -> None:
    """
    Activates the tenant for the context of the query.
    """
    set_schema(tenant_name)


def deativate_schema() -> None:
    """
    Deactivates the tenant for the context of the query.
    """
    set_schema(None)
