import sys
from functools import wraps
from typing import Any, NoReturn, TypeVar

from alembic.util import CommandError
from loguru import logger

T = TypeVar("T")


def catch_errors(fn: T) -> T:
    @wraps(fn)  # type: ignore
    def wrap(*args: Any, **kwargs: Any) -> NoReturn:
        try:
            fn(*args, **kwargs)  # type: ignore
        except (CommandError, RuntimeError) as exc:
            logger.error(f"Error: {str(exc)}")
            sys.exit(1)

    return wrap  # type: ignore


def add_migration_directory_option(fn: Any) -> Any:
    import click

    def callback(ctx: Any, param: str, value: str | None) -> None:
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
        callback=callback,
    )(fn)


def add_force_field_nullable_option(fn: Any) -> Any:
    import click

    return click.option(
        "--null-field",
        "--nf",
        multiple=True,
        default=(),
        help='Force field being nullable. Syntax model:field or ":field" for auto-detection of models with such a field.',
    )(fn)
