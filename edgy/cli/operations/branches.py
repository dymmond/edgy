"""
Client to interact with Edgy models and migrations.
"""

from sayer import command

from ..base import branches as _branches
from ..common_params import VerboseOption
from ..decorators import add_migration_directory_option


@add_migration_directory_option
@command
def branches(verbose: VerboseOption) -> None:
    """Show current branch points"""
    _branches(verbose)
