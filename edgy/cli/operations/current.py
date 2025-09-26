import sayer

from edgy.cli.base import current as _current
from edgy.cli.decorators import add_migration_directory_option

from ..common_params import VerboseOption


@add_migration_directory_option
@sayer.command
def current(verbose: VerboseOption) -> None:
    """Display the current revision for each database."""
    _current(verbose)
