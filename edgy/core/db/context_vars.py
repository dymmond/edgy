from contextvars import ContextVar
from typing import Union

SCHEMA: ContextVar[str] = ContextVar("schema", default=None)
TENANT: ContextVar[str] = ContextVar("tenant", default=None)


def get_tenant() -> str:
    """
    Gets the current active tenant in the context.
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
