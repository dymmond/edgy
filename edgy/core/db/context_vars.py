from contextvars import ContextVar
from typing import TYPE_CHECKING, Literal, Optional, Union

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
# for bw compatibility
SHEMA = SCHEMA


def get_tenant() -> Union[str, None]:
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


def get_schema() -> Union[str, None]:
    return SCHEMA.get()


def set_schema(value: Union[str, None]) -> None:
    SCHEMA.set(value)
