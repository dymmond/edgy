"""
Client to interact with Edgy models and migrations.
"""

import inspect
import sys
import typing
from functools import wraps

import click

from edgy.cli.constants import (
    APP_PARAMETER,
    EXCLUDED_COMMANDS,
    HELP_PARAMETER,
    IGNORE_COMMANDS,
)
from edgy.cli.env import MigrationEnv
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
from edgy.core.terminal import Print
from edgy.exceptions import CommandEnvironmentError

printer = Print()


class EdgyGroup(click.Group):
    """Edgy command group with extras for the commands"""

    def add_command(self, cmd: click.Command, name: typing.Optional[str] = None) -> None:
        if cmd.callback:
            cmd.callback = self.wrap_args(cmd.callback)
        return super().add_command(cmd, name)

    def wrap_args(self, func: typing.Any) -> typing.Any:
        params = inspect.signature(func).parameters

        @wraps(func)
        def wrapped(ctx: click.Context, /, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            scaffold = ctx.ensure_object(MigrationEnv)
            if "env" in params:
                kwargs["env"] = scaffold
            return func(*args, **kwargs)

        return click.pass_context(wrapped)

    def invoke(self, ctx: click.Context) -> typing.Any:
        """
        Migrations can be ignored depending of the functionality from what is being
        called.
        """
        path = ctx.params.get("path", None)

        # Process any settings
        if HELP_PARAMETER not in sys.argv and not any(
            value in sys.argv for value in EXCLUDED_COMMANDS
        ):
            try:
                migration = MigrationEnv()
                app_env = migration.load_from_env(path=path)
                ctx.obj = app_env
            except CommandEnvironmentError as e:
                if not any(value in sys.argv for value in IGNORE_COMMANDS):
                    printer.write_error(str(e))
                    sys.exit(1)
        return super().invoke(ctx)


@click.group(cls=EdgyGroup)
@click.option(
    APP_PARAMETER,
    "path",
    help="Module path to the application to generate the migrations. In a module:path format.",
)
@click.pass_context
def edgy_cli(ctx: click.Context, path: typing.Optional[str]) -> None:
    """Performs database migrations"""
    ...


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
