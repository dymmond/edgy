from contextvars import ContextVar
from typing import TYPE_CHECKING, Type, Union

if TYPE_CHECKING:
    from edgy import Model, QuerySet

SCHEMA: ContextVar[str] = ContextVar("schema", default=None)
TENANT: ContextVar[str] = ContextVar("tenant", default=None)
QUERY: ContextVar[str] = ContextVar("query", default=False)


def get_tenant() -> str:
    """
    Gets the current active tenant in the context.
    """
    return TENANT.get()


def get_new_query() -> str:
    """
    Gets the current query in the context.
    """
    return TENANT.get()


def get_context_db_schema() -> str:
    """
    Gets the db schema from the context.

    If a global tenant is set, then it ignore the context schema and sets the tenant
    to global.
    """
    if get_tenant():
        return get_tenant()
    return SCHEMA.get()


def set_context_query(value: Union[str, None]) -> None:
    """
    Set the value of the query for the context.
    """
    QUERY.set(value)


def set_context_db_schema(value: Union[str, None]) -> None:
    """
    Set the value of the db schema for the context.
    """
    SCHEMA.set(value)


def set_tenant(value: Union[str, None]) -> None:
    """
    Sets the global tenant for the context of the queries.
    When a global tenant is set the `get_context_schema` -> `SCHEMA` is ignored.
    """
    TENANT.set(value)


def set_user_tenant(
    queryset: "QuerySet", model_class: Type["Model"], value: Union[str, None]
) -> "QuerySet":
    """
    Returns a new queryset object pointing to the desired schema of the
    using.
    """
    return queryset.__class__(model_class=model_class, using_schema=value)
