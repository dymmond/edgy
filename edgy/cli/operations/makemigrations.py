"""
Client to interact with Edgy models and migrations.
"""

from typing import Annotated

from sayer import Option, command

from ..base import revision as _revision
from ..common_params import (
    DirectoryOption,
    ExtraArgOption,
    ForceNullFieldOption,
    MessageOption,
    SQLOption,
)


@command
def makemigrations(
    message: MessageOption,
    sql: SQLOption,
    head: Annotated[
        str,
        Option(
            default="head",
            help=("Specify head revision or <branchname>@head to base new revision on."),
        ),
    ],
    splice: Annotated[
        bool,
        Option(
            False,
            is_flag=True,
            help=('Allow a non-head revision as the "head" to splice onto.'),
        ),
    ],
    branch_label: Annotated[
        str | None,
        Option(required=False, help="Specify a branch label to apply to the new revision"),
    ],
    rev_id: Annotated[
        str | None,
        Option(required=False, help="Specify a hardcoded revision id instead of generating one."),
    ],
    version_path: Annotated[
        str | None,
        Option(
            required=False,
            help="Specify specific path from config for version file.",
        ),
    ],
    arg: ExtraArgOption,
    null_field: ForceNullFieldOption,
    directory: DirectoryOption,
) -> None:
    """Autogenerate a new revision file (Alias for 'revision --autogenerate')"""
    _revision(
        message=message,
        sql=sql,
        head=head,
        splice=splice,
        branch_label=branch_label,
        version_path=version_path,
        revision_id=rev_id,
        arg=arg,
        null_fields=null_field,
        autogenerate=True,
    )
