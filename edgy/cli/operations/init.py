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
    """
    Repository template to use (default is "default")'

    The options are:

    - default: The default template

    - plain: A plain template with no environment or version files

    - sequencial: A template with a sequencial versioning scheme. E.g. 0001_initial, 0002_second,
    etc.

    Example:

        edgy init -t sequencial
    """
    _init(template, package)
