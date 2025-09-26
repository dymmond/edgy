import sayer

from edgy.cli.base import stamp as _stamp
from edgy.cli.decorators import add_migration_directory_option

from ..common_params import RevisionHeadArgument, SQLOption, TagOption


@add_migration_directory_option
@sayer.command
def stamp(
    sql: SQLOption,
    tag: TagOption,
    revision: RevisionHeadArgument,
) -> None:
    """'stamp' the revision table with the given revision; don't run any
    migrations"""
    _stamp(revision, sql, tag)
