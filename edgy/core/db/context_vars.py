from contextvars import ContextVar
from typing import Any

CONTEXT_SCHEMA: ContextVar[str] = ContextVar("schema", default=None)


def get_context_db_schema() -> str:
    """
    Gets the db schema from the context.
    """
    return CONTEXT_SCHEMA.get()


def set_context_db_schema(value: Any) -> None:
    """
    Gets the db schema from the context.
    """
    CONTEXT_SCHEMA.set(value)
