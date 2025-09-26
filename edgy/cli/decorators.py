from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from click import Command


def add_migration_directory_option(cmd: Command) -> Any:
    import click

    # is there a better way using sayer?

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
    )(cmd)
