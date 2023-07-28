import sys
from functools import wraps
from typing import Any, Callable, TypeVar

from alembic.util import CommandError
from loguru import logger

T = TypeVar("T")


def catch_errors(fn: Callable) -> T:
    @wraps(fn)
    def wrap(*args: Any, **kwargs: Any) -> T:
        try:
            fn(*args, **kwargs)
        except (CommandError, RuntimeError) as exc:
            logger.error(f"Error: {str(exc)}")
            sys.exit(1)

    return wrap
