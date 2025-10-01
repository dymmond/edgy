import sayer

from edgy.cli.base import check as _check

from ..common_params import DirectoryOption


@sayer.command
def check(directory: DirectoryOption) -> None:
    """Check if there are any new operations to migrate"""
    _check()
