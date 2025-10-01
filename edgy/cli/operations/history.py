from typing import Annotated

import sayer

from edgy.cli.base import history as _history

from ..common_params import DirectoryOption, VerboseOption


@sayer.command
def history(
    rev_range: Annotated[
        str,
        sayer.Option(
            None, "-r", "--rev-range", help="Specify a revision range; format is [start]:[end]"
        ),
    ],
    verbose: VerboseOption,
    indicate_current: Annotated[
        bool,
        sayer.Option(
            False,
            "-i",
            is_flag=True,
            help=("Indicate current version (Alembic 0.9.9 or greater is required)"),
        ),
    ],
    directory: DirectoryOption,
) -> None:
    """List changeset scripts in chronological order."""
    _history(rev_range, verbose, indicate_current)
