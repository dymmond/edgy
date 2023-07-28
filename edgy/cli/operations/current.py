import click

from edgy.cli.base import current as _current
from edgy.cli.env import MigrationEnv


@click.option(
    "-d",
    "--directory",
    default=None,
    help=('Migration script directory (default is "migrations")'),
)
@click.option("-v", "--verbose", is_flag=True, help="Use more verbose output")
@click.command()
def current(env: MigrationEnv, directory: str, verbose: bool) -> None:
    """Display the current revision for each database."""
    _current(env.app, directory, verbose)
