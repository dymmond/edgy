"""
Client to interact with Edgy models and migrations.
"""

from __future__ import annotations

import typing

import click
from sayer import Sayer
from sayer.params import Option

from edgy import __version__
from edgy.cli.groups import DirectiveGroup
from edgy.cli.operations import (
    admin_serve,
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

help_text = """
Edgy command line tool allowing to run Edgy native directives.

How to run Edgy native: `edgy init`. Or any other Edgy native command.

    Example: `edgy shell`

"""


edgy_cli = Sayer(
    name="Edgy",
    help=help_text,
    add_version_option=True,
    version=__version__,
    group_class=DirectiveGroup,
)


@edgy_cli.callback(invoke_without_command=True)
def edgy_callback(
    ctx: click.Context,
    app: typing.Annotated[
        str,
        Option(
            required=False,
            help="Module path to the Edgy application. In a module.submodule format.",
        ),
    ],
    path: typing.Annotated[
        str | None,
        Option(
            required=False,
            help="A path to a Python file or package directory with ([blue]__init__.py[/blue] files) containing a [bold]Edgy[/bold] app. If not provided, Edgy will try to discover from cwd.",
        ),
    ],
) -> None: ...


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
edgy_cli.add_command(admin_serve, name="admin_serve")
