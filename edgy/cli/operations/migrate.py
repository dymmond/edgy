import sayer

from edgy.cli.base import upgrade as _upgrade
from edgy.cli.decorators import add_migration_directory_option

from ..common_params import ExtraArgOption, RevisionHeadArgument, SQLOption, TagOption


@add_migration_directory_option
@sayer.command(context_settings={"ignore_unknown_options": True})  # type: ignore
def migrate(
    sql: SQLOption, tag: TagOption, arg: ExtraArgOption, revision: RevisionHeadArgument
) -> None:
    """
    Upgrades to the latest version or to a specific version
    provided by the --tag.
    """
    _upgrade(revision, sql, tag, arg)
