import sayer

from edgy.cli.base import stamp as _stamp

from ..common_params import DirectoryOption, RevisionHeadArgument, SQLOption, TagOption


@sayer.command
def stamp(
    sql: SQLOption, tag: TagOption, revision: RevisionHeadArgument, directory: DirectoryOption
) -> None:
    """'stamp' the revision table with the given revision; don't run any
    migrations"""
    _stamp(revision, sql, tag)
