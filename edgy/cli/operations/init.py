import click

from edgy.cli.base import init as _init
from edgy.cli.decorators import add_migration_directory_option


@add_migration_directory_option
@click.option(
    "-t", "--template", default=None, help=('Repository template to use (default is "default")')
)
@click.option(
    "--package",
    is_flag=True,
    help=("Write empty __init__.py files to the environment and version locations"),
)
@click.command(name="init")
def init(template: str, package: bool) -> None:
    """Creates a new migration repository."""
    _init(template, package)
