from typing import Annotated

import sayer

from edgy.cli.base import downgrade as _downgrade
from edgy.cli.decorators import add_migration_directory_option

from ..common_params import ExtraArgOption, SQLOption, TagOption


@add_migration_directory_option
@sayer.command(context_settings={"ignore_unknown_options": True})  # type: ignore
def downgrade(
    sql: SQLOption,
    tag: TagOption,
    arg: ExtraArgOption,
    revision: Annotated[str, sayer.Argument("-1")],
) -> None:
    """Revert to a previous version"""
    _downgrade(revision, sql, tag, arg)
