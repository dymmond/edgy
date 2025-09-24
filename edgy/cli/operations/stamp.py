from typing import Annotated

import sayer

from edgy.cli.base import stamp as _stamp
from edgy.cli.decorators import add_migration_directory_option


@add_migration_directory_option
@sayer.command
def stamp(
    sql: Annotated[
        bool,
        sayer.Option(
            is_flag=True, help=("Don't emit SQL to database - dump to standard output instead.")
        ),
    ],
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
