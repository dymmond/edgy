from contextvars import ContextVar

CONTEXT_SCHEMA: ContextVar[str] = ContextVar("schema", default=None)
