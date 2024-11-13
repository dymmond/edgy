import click

from edgy.cli.base import heads as _heads
from edgy.cli.decorators import add_migration_directory_option


@add_migration_directory_option
@click.option("-v", "--verbose", is_flag=True, help="Use more verbose output")
@click.option(
    "--resolve-dependencies", is_flag=True, help="Treat dependency versions as down revisions"
)
@click.command()
def heads(verbose: bool, resolve_dependencies: bool) -> None:
    """Show current available heads in the script directory"""
    _heads(verbose, resolve_dependencies)
