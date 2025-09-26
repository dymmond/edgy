import sayer

from edgy.cli.base import show as _show
from edgy.cli.decorators import add_migration_directory_option

from ..common_params import RevisionHeadArgument


@add_migration_directory_option
@sayer.command
def show(revision: RevisionHeadArgument) -> None:
    """Show the revision denoted by the given symbol."""
    _show(revision)
