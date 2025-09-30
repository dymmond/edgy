import sayer

from edgy.cli.base import upgrade as _upgrade

from ..common_params import (
    DirectoryOption,
    ExtraArgOption,
    RevisionHeadArgument,
    SQLOption,
    TagOption,
)


@sayer.command(context_settings={"ignore_unknown_options": True})
def migrate(
    sql: SQLOption,
    tag: TagOption,
    arg: ExtraArgOption,
    revision: RevisionHeadArgument,
    directory: DirectoryOption,
) -> None:
    """
    Upgrades to the latest version or to a specific version
    provided by the --tag.
    """
    _upgrade(revision, sql, tag, arg)
