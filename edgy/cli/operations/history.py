import click

from edgy.cli.base import history as _history
from edgy.cli.decorators import add_migration_directory_option


@add_migration_directory_option
@click.option(
    "-r", "--rev-range", default=None, help="Specify a revision range; format is [start]:[end]"
)
@click.option("-v", "--verbose", is_flag=True, help="Use more verbose output")
@click.option(
    "-i",
    "--indicate-current",
    is_flag=True,
    help=("Indicate current version (Alembic 0.9.9 or greater is required)"),
)
@click.command()
def history(rev_range: str, verbose: bool, indicate_current: bool) -> None:
    """List changeset scripts in chronological order."""
    _history(rev_range, verbose, indicate_current)
