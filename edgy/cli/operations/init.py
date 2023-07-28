import click

from edgy.cli.base import init as _init
from edgy.cli.env import MigrationEnv


@click.option(
    "-d",
    "--directory",
    default=None,
    help=('Migration script directory (default is "migrations")'),
)
@click.option(
    "-t", "--template", default=None, help=('Repository template to use (default is "flask")')
)
@click.option(
    "--package",
    is_flag=True,
    help=("Write empty __init__.py files to the environment and " "version locations"),
)
@click.command(name="init")
def init(env: MigrationEnv, directory: str, template: str, package: bool) -> None:
    """Creates a new migration repository."""
    _init(env.app, directory, template, package)
