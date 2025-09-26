from typing import Annotated

import sayer

from edgy.cli.base import history as _history
from edgy.cli.decorators import add_migration_directory_option

from ..common_params import VerboseOption


@add_migration_directory_option
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
) -> None:
    """List changeset scripts in chronological order."""
    _history(rev_range, verbose, indicate_current)
