from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Literal, Optional, Union
from warnings import warn

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType
    from edgy.core.db.querysets.base import QuerySet

CURRENT_INSTANCE: ContextVar[Optional[Union["BaseModelType", "QuerySet"]]] = ContextVar(
    "CURRENT_INSTANCE", default=None
)
CURRENT_MODEL_INSTANCE: ContextVar[Optional["BaseModelType"]] = ContextVar(
    "CURRENT_MODEL_INSTANCE", default=None
)
CURRENT_PHASE: ContextVar[str] = ContextVar("CURRENT_PHASE", default="")
EXPLICIT_SPECIFIED_VALUES: ContextVar[Optional[set[str]]] = ContextVar(
    "EXPLICIT_SPECIFIED_VALUES", default=None
)
MODEL_GETATTR_BEHAVIOR: ContextVar[Literal["passdown", "load", "coro"]] = ContextVar(
    "MODEL_GETATTR_BEHAVIOR", default="load"
)
TENANT: ContextVar[str] = ContextVar("tenant", default=None)
SCHEMA: ContextVar[str] = ContextVar("SCHEMA", default=None)
# for backward compatibility
SHEMA = SCHEMA


def get_tenant() -> Union[str, None]:
    """
    Gets the current active tenant in the context.
    """
    return TENANT.get()


def set_tenant(value: Union[str, None]) -> Token:
    """
    Sets the global tenant for the context of the queries.
    When a global tenant is set the `get_schema` -> `SCHEMA` is ignored.
    """
    warn(
        "`set_tenant` is deprecated use `with_tenant` instead. WARNING: this function is broken and doesn't reset the tenant.",
        DeprecationWarning,
        stacklevel=2,
    )
    # why deprecating this? It overwrites schema and can lead to hard to debug issues when the scope isn't resetted.

    return TENANT.set(value)


@contextmanager
def with_tenant(tenant: Union[str, None]) -> None:
    """
    Sets the global tenant for the context of the queries.
    When a global tenant is set the `get_schema` -> `SCHEMA` is ignored.
    """
    # Why preferring to a set_tenant?
    # Set_tenant overwrites schema and can lead to hard to debug issues when the scope isn't resetted
    # while this has a limited scope
    # set_tenant affects the get_schema method.
    token = TENANT.set(tenant)
    try:
        yield
    finally:
        TENANT.reset(token)


def get_schema(check_tenant: bool = True) -> Union[str, None]:
    if check_tenant:
        tenant = get_tenant()
        if tenant is not None:
            return tenant
    return SCHEMA.get()


def set_schema(value: Union[str, None]) -> Token:
    """Set the schema and return the token for resetting. Manual way of with_schema."""

    return SCHEMA.set(value)


@contextmanager
def with_schema(schema: Union[str, None]) -> None:
    token = SCHEMA.set(schema)
    try:
        yield
    finally:
        SCHEMA.reset(token)
