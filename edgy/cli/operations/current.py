import click

from edgy.cli.base import current as _current
from edgy.cli.decorators import add_migration_directory_option


@add_migration_directory_option
@click.option("-v", "--verbose", is_flag=True, help="Use more verbose output")
@click.command()
def current(verbose: bool) -> None:
    """Display the current revision for each database."""
    _current(verbose)
