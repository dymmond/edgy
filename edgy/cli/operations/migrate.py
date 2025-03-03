from typing import Any

import click

from edgy.cli.base import upgrade as _upgrade
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
@click.argument("revision", default="head")
def migrate(sql: bool, tag: str, arg: Any, revision: str) -> None:
    """
    Upgrades to the latest version or to a specific version
    provided by the --tag.
    """
    _upgrade(revision, sql, tag, arg)
