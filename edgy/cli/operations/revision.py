from typing import Annotated

from sayer import Option, command

from edgy.cli.base import revision as _revision
from edgy.cli.decorators import add_migration_directory_option

from ..common_params import ExtraArgOption, ForceNullFieldOption, MessageOption, SQLOption


@add_migration_directory_option
@command(context_settings={"ignore_unknown_options": True})  # type: ignore
def revision(
    message: MessageOption,
    autogenerate: Annotated[
        bool,
        Option(
            False,
            is_flag=True,
            help=(
                "Populate revision script with candidate migration "
                "operations, based on comparison of database to model."
            ),
        ),
    ],
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
        Option(None, help="Specify a branch label to apply to the new revision."),
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
    """Create a new revision file."""
    _revision(
        message=message,
        autogenerate=autogenerate,
        sql=sql,
        head=head,
        splice=splice,
        branch_label=branch_label,
        version_path=version_path,
        revision_id=rev_id,
        arg=arg,
        null_fields=null_field,
    )
