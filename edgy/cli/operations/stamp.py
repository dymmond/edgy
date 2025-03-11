import click

from edgy.cli.base import stamp as _stamp
from edgy.cli.decorators import add_migration_directory_option


@add_migration_directory_option
@click.option(
    "--sql", is_flag=True, help=("Don't emit SQL to database - dump to standard output instead")
)
@click.option(
    "--tag", default=None, help=('Arbitrary "tag" name - can be used by custom env.py scripts')
)
@click.argument("revision", default="head")
@click.command()
def stamp(sql: bool, tag: str, revision: str) -> None:
    """'stamp' the revision table with the given revision; don't run any
    migrations"""
    _stamp(revision, sql, tag)
