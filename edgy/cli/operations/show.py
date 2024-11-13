import click

from edgy.cli.base import show as _show
from edgy.cli.decorators import add_migration_directory_option


@add_migration_directory_option
@click.command()
@click.argument("revision", default="head")
def show(revision: str) -> None:
    """Show the revision denoted by the given symbol."""
    _show(revision)
