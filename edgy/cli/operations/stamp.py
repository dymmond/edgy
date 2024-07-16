import click

from edgy.cli.base import stamp as _stamp
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
@click.argument("revision", default="head")
@click.command()
def stamp(env: MigrationEnv, directory: str, sql: bool, tag: str, revision: str) -> None:
    """'stamp' the revision table with the given revision; don't run any
    migrations"""
    _stamp(env.app, directory, revision, sql, tag)
