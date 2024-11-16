"""
Client to interact with Edgy models and migrations.
"""

import click

from edgy.cli.base import branches as _branches
from edgy.cli.decorators import add_migration_directory_option


@add_migration_directory_option
@click.option("-v", "--verbose", is_flag=True, help="Use more verbose output")
@click.command()
def branches(verbose: bool) -> None:
    """Show current branch points"""
    _branches(verbose)
