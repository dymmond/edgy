from typing import Any

import click

from edgy.cli.base import downgrade as _downgrade
from edgy.cli.decorators import add_migration_directory_option


@add_migration_directory_option
@click.option(
    "--sql", is_flag=True, help=("Don't emit SQL to database - dump to standard output instead")
)
@click.option(
    "--tag", default=None, help=('Arbitrary "tag" name - can be used by custom env.py scripts')
)
@click.option(
    "-x", "--arg", multiple=True, help="Additional arguments consumed by custom env.py scripts"
)
@click.command(context_settings={"ignore_unknown_options": True})
@click.argument("revision", default="-1")
def downgrade(sql: bool, tag: str, arg: Any, revision: str) -> None:
    """Revert to a previous version"""
    _downgrade(revision, sql, tag, arg)
