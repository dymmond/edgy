from typing import Annotated

import sayer

from edgy.cli.base import merge as _merge

from ..common_params import DirectoryOption, MessageOption


@sayer.command
def merge(
    message: MessageOption,
    branch_label: Annotated[
        str,
        sayer.Option(None, help="Specify a branch label to apply to the new revision"),
    ],
    rev_id: Annotated[
        str, sayer.Option(None, help="Specify a hardcoded revision id instead of generating one.")
    ],
    revisions: Annotated[list[str], sayer.Argument(nargs=-1)],
    directory: DirectoryOption,
) -> None:
    """Merge two revisions together, creating a new revision file"""
    _merge(revisions, message, branch_label, rev_id)
