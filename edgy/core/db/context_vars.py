from contextvars import ContextVar

CONTEXT_SCHEMA: ContextVar[str] = ContextVar("schema", default=None)


def get_context_db_schema() -> str:
    """
    Gets the db schema from the context.
    """
    return CONTEXT_SCHEMA.get()
