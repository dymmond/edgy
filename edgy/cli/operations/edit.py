from typing import Annotated

import sayer

from edgy.cli.base import edit as _edit
from edgy.cli.decorators import add_migration_directory_option


@add_migration_directory_option
@sayer.command
def edit(revision: Annotated[str, sayer.Argument("head")]) -> None:
    """Edit a revision file"""
    _edit(revision)
