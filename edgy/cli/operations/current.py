import sayer

from edgy.cli.base import current as _current

from ..common_params import DirectoryOption, VerboseOption


@sayer.command
def current(verbose: VerboseOption, directory: DirectoryOption) -> None:
    """Display the current revision for each database."""
    _current(verbose)
