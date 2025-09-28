import sayer

from edgy.cli.base import edit as _edit

from ..common_params import DirectoryOption, RevisionHeadArgument


@sayer.command
def edit(revision: RevisionHeadArgument, directory: DirectoryOption) -> None:
    """Edit a revision file"""
    _edit(revision)
