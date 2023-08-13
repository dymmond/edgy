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


def get_context_db_schema() -> Union[str, None]:
    """
    Gets the db schema from the context.

    If a global tenant is set, then it ignore the context schema and sets the tenant
    to global.
    """
    if get_tenant():
        return get_tenant()
    return None


def set_tenant(value: Union[str, None]) -> None:
    """
    Sets the global tenant for the context of the queries.
    When a global tenant is set the `get_context_schema` -> `SCHEMA` is ignored.
    """
    TENANT.set(value)


def set_queryset_schema(
    queryset: "QuerySet",
    model_class: Type["Model"],
    value: Union[str, None],
    is_global: bool = False,
) -> "QuerySet":
    """
    Returns a new queryset object pointing to the desired schema of the
    using.
    """
    return queryset.__class__(
        model_class=model_class,
        using_schema=value,
        is_global=is_global,
        table=model_class.table_schema(value),
    )
