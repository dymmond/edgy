import click

from edgy.cli.base import history as _history
from edgy.cli.env import MigrationEnv


@click.option(
    "-d",
    "--directory",
    default=None,
    help=('Migration script directory (default is "migrations")'),
)
@click.option(
    "-r", "--rev-range", default=None, help="Specify a revision range; format is [start]:[end]"
)
@click.option("-v", "--verbose", is_flag=True, help="Use more verbose output")
@click.option(
    "-i",
    "--indicate-current",
    is_flag=True,
    help=("Indicate current version (Alembic 0.9.9 or greater is " "required)"),
)
@click.command()
def history(
    env: MigrationEnv, directory: str, rev_range: str, verbose: bool, indicate_current: bool
) -> None:
    """List changeset scripts in chronological order."""
    _history(env.app, directory, rev_range, verbose, indicate_current)
