from typing import Any

import click

from edgy.cli.base import upgrade as _upgrade
from edgy.cli.env import MigrationEnv


@click.option(
    "-d",
    "--directory",
    default=None,
    help=('Migration script directory (default is "migrations")'),
)
@click.option(
    "--sql", is_flag=True, help=("Don't emit SQL to database - dump to standard output " "instead")
)
@click.option(
    "--tag", default=None, help=('Arbitrary "tag" name - can be used by custom env.py ' "scripts")
)
@click.option(
    "-x", "--arg", multiple=True, help="Additional arguments consumed by custom env.py scripts"
)
@click.command()
@click.argument("revision", default="head")
def migrate(
    env: MigrationEnv, directory: str, sql: bool, tag: str, arg: Any, revision: str
) -> None:
    """
    Upgrades to the latest version or to a specific version
    provided by the --tag.
    """
    _upgrade(env.app, directory, revision, sql, tag, arg)
