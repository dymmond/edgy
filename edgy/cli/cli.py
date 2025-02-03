"""
Client to interact with Edgy models and migrations.
"""

import click

from edgy import __version__
from edgy.cli.decorators import add_app_module_option
from edgy.cli.operations import (
    check,
    current,
    downgrade,
    edit,
    heads,
    history,
    init,
    inspect_db,
    list_templates,
    makemigrations,
    merge,
    migrate,
    revision,
    shell,
    show,
    stamp,
)


@add_app_module_option
@click.group()
@click.version_option(__version__)
def edgy_cli(path: str = "") -> None:
    """Performs database migrations"""


edgy_cli.add_command(list_templates)
edgy_cli.add_command(init, name="init")
edgy_cli.add_command(revision, name="revision")
edgy_cli.add_command(makemigrations, name="makemigrations")
edgy_cli.add_command(edit, name="edit")
edgy_cli.add_command(merge, name="merge")
edgy_cli.add_command(migrate, name="migrate")
edgy_cli.add_command(downgrade, name="downgrade")
edgy_cli.add_command(show, name="show")
edgy_cli.add_command(history, name="history")
edgy_cli.add_command(heads, name="heads")
edgy_cli.add_command(current, name="current")
edgy_cli.add_command(stamp, name="stamp")
edgy_cli.add_command(check, name="check")
edgy_cli.add_command(shell, name="shell")
edgy_cli.add_command(inspect_db, name="inspectdb")
