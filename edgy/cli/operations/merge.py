from typing import Any

import click

from edgy.cli.base import merge as _merge
from edgy.cli.env import MigrationEnv


@click.option(
    "-d",
    "--directory",
    default=None,
    help=('Migration script directory (default is "migrations")'),
)
@click.option("-m", "--message", default=None, help="Merge revision message")
@click.option(
    "--branch-label", default=None, help=("Specify a branch label to apply to the new revision")
)
@click.option(
    "--rev-id", default=None, help=("Specify a hardcoded revision id instead of generating " "one")
)
@click.command()
@click.argument("revisions", nargs=-1)
def merge(
    env: MigrationEnv, directory: str, message: str, branch_label: str, rev_id: str, revisions: Any
) -> None:
    """Merge two revisions together, creating a new revision file"""
    _merge(env.app, directory, revisions, message, branch_label, rev_id)
