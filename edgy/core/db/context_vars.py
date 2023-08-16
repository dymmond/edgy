from contextvars import ContextVar
from typing import TYPE_CHECKING, Type, Union

if TYPE_CHECKING:
    from edgy import Database, Model, QuerySet

TENANT: ContextVar[str] = ContextVar("tenant", default=None)


def get_tenant() -> str:
    """
    Gets the current active tenant in the context.
    """
    return TENANT.get()


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
) -> "QuerySet":
    """
    Returns a new queryset object pointing to the desired schema of the
    using.
    """
    return queryset.__class__(
        model_class=model_class,
        using_schema=value,
        table=model_class.table_schema(value),
    )


def set_queryset_database(
    queryset: "QuerySet",
    model_class: Type["Model"],
    database: Type["Database"],
    schema: Union[str, None] = None,
) -> "QuerySet":
    """
    Returns a new queryset object pointing to the desired schema of the
    using.
    """
    if not schema:
        return queryset.__class__(
            model_class=model_class,
            database=database,
            table=model_class.table_schema(schema),
        )
    return queryset.__class__(model_class=model_class, database=database)
