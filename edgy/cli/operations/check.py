import click

from edgy.cli.base import check as _check
from edgy.cli.env import MigrationEnv


@click.option(
    "-d",
    "--directory",
    default=None,
    help=('Migration script directory (default is "migrations")'),
)
@click.command()
def check(env: MigrationEnv, directory: str) -> None:
    """Check if there are any new operations to migrate"""
    _check(env.app, directory)
