"""
Client to interact with Edgy models and migrations.
"""

import click

from edgy.cli.base import branches as _branches
from edgy.cli.env import MigrationEnv


@click.option(
    "-d",
    "--directory",
    default=None,
    help=('Migration script directory (default is "migrations")'),
)
@click.option("-v", "--verbose", is_flag=True, help="Use more verbose output")
@click.command()
def branches(env: MigrationEnv, directory: str, verbose: bool) -> None:
    """Show current branch points"""
    _branches(env.app, directory, verbose)
