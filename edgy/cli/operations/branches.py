"""
Client to interact with Edgy models and migrations.
"""

from sayer import command

from ..base import branches as _branches
from ..common_params import DirectoryOption, VerboseOption


@command
def branches(verbose: VerboseOption, directory: DirectoryOption) -> None:
    """Show current branch points"""
    _branches(verbose)
