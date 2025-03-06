from typing import Any, Union

import click

from edgy.cli.base import revision as _revision
from edgy.cli.decorators import add_force_field_nullable_option, add_migration_directory_option


@add_force_field_nullable_option
@add_migration_directory_option
@click.option("-m", "--message", default=None, help="Revision message")
@click.option(
    "--autogenerate",
    is_flag=True,
    help=(
        "Populate revision script with candidate migration "
        "operations, based on comparison of database to model"
    ),
)
@click.option(
    "--sql", is_flag=True, help=("Don't emit SQL to database - dump to standard output instead")
)
@click.option(
    "--head",
    default="head",
    help=("Specify head revision or <branchname>@head to base new revision on"),
)
@click.option(
    "--splice", is_flag=True, help=('Allow a non-head revision as the "head" to splice onto')
)
@click.option(
    "--branch-label", default=None, help=("Specify a branch label to apply to the new revision")
)
@click.option(
    "--version-path", default=None, help=("Specify specific path from config for version file")
)
@click.option(
    "--rev-id", default=None, help=("Specify a hardcoded revision id instead of generating one")
)
@click.option(
    "-x", "--arg", multiple=True, help="Additional arguments consumed by custom env.py scripts"
)
@click.command(context_settings={"ignore_unknown_options": True})
def revision(
    message: str,
    autogenerate: bool,
    sql: bool,
    head: str,
    splice: bool,
    branch_label: str,
    version_path: str,
    rev_id: str,
    arg: Any,
    null_field: Union[list[str], tuple[str, ...]],
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
