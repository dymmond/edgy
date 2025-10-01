from typing import Annotated

import sayer

from edgy.cli.base import downgrade as _downgrade

from ..common_params import DirectoryOption, ExtraArgOption, SQLOption, TagOption


@sayer.command(context_settings={"ignore_unknown_options": True})
def downgrade(
    sql: SQLOption,
    tag: TagOption,
    arg: ExtraArgOption,
    revision: Annotated[str, sayer.Argument("-1")],
    directory: DirectoryOption,
) -> None:
    """Revert to a previous version"""
    _downgrade(revision, sql, tag, arg)
