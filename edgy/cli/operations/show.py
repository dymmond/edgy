import sayer

from edgy.cli.base import show as _show

from ..common_params import DirectoryOption, RevisionHeadArgument


@sayer.command
def show(revision: RevisionHeadArgument, directory: DirectoryOption) -> None:
    """Show the revision denoted by the given symbol."""
    _show(revision)
