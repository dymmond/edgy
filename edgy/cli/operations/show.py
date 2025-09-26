from typing import Annotated

import sayer

from edgy.cli.base import show as _show
from edgy.cli.decorators import add_migration_directory_option


@add_migration_directory_option
@sayer.command
def show(revision: Annotated[str, sayer.Argument("head")]) -> None:
    """Show the revision denoted by the given symbol."""
    _show(revision)
