import inspect
import sys
import typing
from functools import wraps

import click

from edgy.cli.constants import HELP_PARAMETER
from edgy.cli.env import EdgyProject
from edgy.cli.operations import check
from edgy.core.terminal import Print
from edgy.exceptions import CommandEnvironmentError

printer = Print()


class EdgyGroup(click.Group):
    """Edgy group with extras for the commands"""

    def add_command(self, cmd: click.Command, name: typing.Optional[str] = None) -> None:
        if cmd.callback:
            cmd.callback = self.wrap_args(cmd.callback)
        return super().add_command(cmd, name)

    def wrap_args(self, func: typing.Any) -> typing.Any:
        params = inspect.signature(func).parameters

        @wraps(func)
        def wrapped(ctx: click.Context, /, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            project = ctx.ensure_object(EdgyProject)
            if "project" in params:
                kwargs["project"] = project
            return func(*args, **kwargs)

        return click.pass_context(wrapped)

    def invoke(self, ctx: click.Context) -> typing.Any:
        if HELP_PARAMETER not in sys.argv:
            try:
                edgy = EdgyProject()
                edgy_project = edgy.find_edgedb_project()
                ctx.obj = edgy_project
            except CommandEnvironmentError as e:
                printer.write_error(str(e))
                sys.exit(1)
            return super().invoke(ctx)


@click.group(cls=EdgyGroup)
@click.pass_context
def edgy_cli(ctx: click.Context) -> None:
    ...


edgy_cli.add_command(check)
