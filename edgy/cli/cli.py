"""
Client to interact with Edgy models and migrations.
"""

from __future__ import annotations

import sys
import typing
from contextlib import suppress
from importlib import import_module
from pathlib import Path

import click
from sayer import Sayer, error
from sayer.params import Option

import edgy
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

from .constants import COMMANDS_WITHOUT_APP, DISCOVERY_PRELOADS

help_text = """
Edgy command line tool allowing to run Edgy native directives.

How to run Edgy native: `edgy init`. Or any other Edgy native command.

    Example: `edgy shell`

"""


edgy_cli = Sayer(
    name="edgy",
    help=help_text,
    add_version_option=True,
    version=edgy.__version__,
)

app_help_text = """
Module path to the Edgy application. In a <module>.<submodule> format.

To detect an app, the instance variable of edgy.monkay must be set when loading.

Alternatively, if none is passed, Edgy will perform the application discovery starting from --path (if specified) or cwd.
"""


@edgy_cli.callback(invoke_without_command=True)
def edgy_callback(
    ctx: click.Context,
    app: typing.Annotated[
        str | None,
        Option(required=False, help=app_help_text, envvar="EDGY_DEFAULT_APP"),
    ],
    path: typing.Annotated[
        str | None,
        Option(
            required=False,
            help="A path to a Python file or package directory with ([blue]__init__.py[/blue] files) containing a [bold]Edgy[/bold] app. If not provided, Edgy will try to discover from cwd.",
        ),
    ],
) -> None:
    if "--help" not in ctx.args:
        cwd = Path.cwd() if path is None else Path(path)
        sys.path.insert(0, str(cwd))

        # try to initialize the config and load preloads when the config is ready
        edgy.monkay.evaluate_settings()
        if ctx.invoked_subcommand not in COMMANDS_WITHOUT_APP:
            if app:
                try:
                    import_module(app)
                except ImportError:
                    error(f'Provided --app parameter or EDGY_DEFAULT_APP is invalid: "{app}"')
                    sys.exit(1)

                if edgy.monkay.instance is None:
                    error(f'Edgy instance still unset after importing "{app}"')
                    sys.exit(1)
            elif edgy.monkay.instance is None:
                # skip when already set by a module preloaded
                found: bool = False

                for preload in DISCOVERY_PRELOADS:
                    with suppress(ImportError):
                        import_module(preload)
                    if typing.cast(typing.Any, edgy.monkay.instance) is not None:
                        found = True
                if not found:
                    for search_path in cwd.iterdir():
                        if "." not in search_path.name and search_path.is_dir():
                            for preload in DISCOVERY_PRELOADS:
                                with suppress(ImportError):
                                    import_module(f"{search_path.name}.{preload}")
                                if typing.cast(typing.Any, edgy.monkay.instance is not None):
                                    found = True
                                    break
                if not found:
                    error("Could not find edgy application via autodiscovery.")
                    sys.exit(1)


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
