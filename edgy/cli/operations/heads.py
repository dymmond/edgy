from typing import Annotated

import sayer

from edgy.cli.base import heads as _heads
from edgy.cli.decorators import add_migration_directory_option

from ..common_params import VerboseOption


@add_migration_directory_option
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
) -> None:
    """Show current available heads in the script directory"""
    _heads(verbose, resolve_dependencies)
