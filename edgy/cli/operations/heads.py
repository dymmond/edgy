from typing import Annotated

import sayer

from edgy.cli.base import heads as _heads

from ..common_params import DirectoryOption, VerboseOption


@sayer.command
def heads(
    verbose: VerboseOption,
    resolve_dependencies: Annotated[
        bool,
        sayer.Option(
            False,
            is_flag=True,
            help="Treat dependency versions as down revisions",
        ),
    ],
    directory: DirectoryOption,
) -> None:
    """Show current available heads in the script directory"""
    _heads(verbose, resolve_dependencies)
