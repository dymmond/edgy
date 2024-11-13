import sys
from functools import wraps
from typing import Any, Optional, TypeVar

from alembic.util import CommandError
from loguru import logger

T = TypeVar("T")


def catch_errors(fn: T) -> T:
    @wraps(fn)  # type: ignore
    def wrap(*args: Any, **kwargs: Any) -> T:
        try:
            fn(*args, **kwargs)  # type: ignore
        except (CommandError, RuntimeError) as exc:
            logger.error(f"Error: {str(exc)}")
            sys.exit(1)

    return wrap  # type: ignore


def add_migration_directory_option(fn):
    import click

    def callback(ctx: Any, param: str, value: Optional[str]) -> None:
        import edgy

        if value is not None:
            edgy.settings.migration_directory = value

    return click.option(
        "-d",
        "--directory",
        default=None,
        help=('Migration script directory (default is "migrations")'),
        expose_value=False,
        is_eager=True,
    )(fn)
