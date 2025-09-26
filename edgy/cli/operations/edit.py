import sayer

from edgy.cli.base import edit as _edit
from edgy.cli.decorators import add_migration_directory_option

from ..common_params import RevisionHeadArgument


@add_migration_directory_option
@sayer.command
def edit(revision: RevisionHeadArgument) -> None:
    """Edit a revision file"""
    _edit(revision)
