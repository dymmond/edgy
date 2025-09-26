from typing import Annotated

import sayer

from edgy.cli.base import stamp as _stamp
from edgy.cli.decorators import add_migration_directory_option

from ..common_params import SQLOption


@add_migration_directory_option
@sayer.command
def stamp(
    sql: SQLOption,
    tag: Annotated[
        str | None,
        sayer.Option(
            default=None,
            help=('Arbitrary "tag" name - can be used by custom env.py scripts.'),
        ),
    ],
    revision: Annotated[str, sayer.Argument(default="head")],
) -> None:
    """'stamp' the revision table with the given revision; don't run any
    migrations"""
    _stamp(revision, sql, tag)
