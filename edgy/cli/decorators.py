from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

if TYPE_CHECKING:
    from click import Command, Context


def add_migration_directory_option(cmd: Command) -> Any:
    from sayer import Option

    @cmd.callback
    def callback(
        ctx: Context,
        directory: Annotated[
            str | None,
            Option(
                None, "-d", type=str, help='Migration script directory (default is "migrations")'
            ),
        ],
    ) -> None:
        import edgy

        if directory is not None:
            edgy.settings.migration_directory = directory

    return cmd
