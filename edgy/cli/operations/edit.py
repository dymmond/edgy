import click

from edgy.cli.base import edit as _edit
from edgy.cli.decorators import add_migration_directory_option


@add_migration_directory_option
@click.command()
@click.argument("revision", default="head")
def edit(revision: str) -> None:
    """Edit a revision file"""
    _edit(revision)
