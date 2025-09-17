from __future__ import annotations

import asyncio
import select
import sys
from typing import TYPE_CHECKING, Any

import click
from monkay.asgi import Lifespan

import edgy
from edgy.cli.operations.shell.enums import ShellOption
from edgy.core.utils.sync import run_sync

if TYPE_CHECKING:
    from edgy.core.connection import Registry


@click.option(
    "--kernel",
    default="ipython",
    type=click.Choice(["ipython", "ptpython"]),
    help="Which shell should start.",
    show_default=True,
)
@click.command()
def shell(kernel: str) -> None:
    """
    Starts an interactive ipython shell with all the models
    and important python libraries.

    This can be used with a Migration class or with EdgyExtra object lookup.
    """
    instance = edgy.monkay.instance
    app, registry = None, None
    if instance is not None:
        app = instance.app
        registry = instance.registry
    if (
        sys.platform != "win32"
        and not sys.stdin.isatty()
        and select.select([sys.stdin], [], [], 0)[0]
    ):
        exec(sys.stdin.read(), globals())
        return

    assert registry is not None
    run_sync(run_shell(app, registry, kernel))
    return None


async def run_shell(app: Any, registry: Registry, kernel: str) -> None:
    """Executes the database shell connection"""

    async with Lifespan(app):
        if kernel == ShellOption.IPYTHON:
            from edgy.cli.operations.shell.ipython import get_ipython

            ipython_shell = get_ipython(app=app, registry=registry)
            # it want its own asyncio.run
            await asyncio.to_thread(ipython_shell)
        else:
            from edgy.cli.operations.shell.ptpython import get_ptpython

            ptpython = get_ptpython(app=app, registry=registry)
            # it maybe want its own asyncio.run
            await asyncio.to_thread(ptpython)
