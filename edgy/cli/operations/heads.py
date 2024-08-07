import click

from edgy.cli.base import heads as _heads
from edgy.cli.env import MigrationEnv


@click.option(
    "-d",
    "--directory",
    default=None,
    help=('Migration script directory (default is "migrations")'),
)
@click.option("-v", "--verbose", is_flag=True, help="Use more verbose output")
@click.option(
    "--resolve-dependencies", is_flag=True, help="Treat dependency versions as down revisions"
)
@click.command()
def heads(env: MigrationEnv, directory: str, verbose: bool, resolve_dependencies: bool) -> None:
    """Show current available heads in the script directory"""
    _heads(env.app, directory, verbose, resolve_dependencies)
