import click

from edgy.cli.base import check as _check
from edgy.cli.decorators import add_migration_directory_option


@add_migration_directory_option
@click.command()
def check() -> None:
    """Check if there are any new operations to migrate"""
    _check()
