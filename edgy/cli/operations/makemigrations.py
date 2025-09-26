"""
Client to interact with Edgy models and migrations.
"""

from typing import Annotated

from sayer import Option, command

from ..base import migrate as _migrate
from ..common_params import ExtraArgOption, ForceNullFieldOption, MessageOption, SQLOption
from ..decorators import add_migration_directory_option


@add_migration_directory_option
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
        str,
        Option(None, help="Specify a branch label to apply to the new revision"),
    ],
    rev_id: Annotated[
        str, Option(None, help="Specify a hardcoded revision id instead of generating one.")
    ],
    version_path: Annotated[
        str,
        Option(
            None,
            help="Specify specific path from config for version file.",
        ),
    ],
    arg: ExtraArgOption,
    null_field: ForceNullFieldOption,
) -> None:
    """Autogenerate a new revision file (Alias for 'revision --autogenerate')"""
    _migrate(
        message=message,
        sql=sql,
        head=head,
        splice=splice,
        branch_label=branch_label,
        version_path=version_path,
        revision_id=rev_id,
        arg=arg,
        null_fields=null_field,
    )
