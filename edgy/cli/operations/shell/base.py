from __future__ import annotations

import asyncio
import select
import sys
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Callable, Optional

import click

import edgy
from edgy.cli.operations.shell.enums import ShellOption
from edgy.core.events import AyncLifespanContextManager
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

    on_startup = getattr(app, "on_startup", [])
    on_shutdown = getattr(app, "on_shutdown", [])
    lifespan = getattr(app, "lifespan", None)
    lifespan = handle_lifespan_events(
        on_startup=on_startup, on_shutdown=on_shutdown, lifespan=lifespan
    )
    assert registry is not None
    run_sync(run_shell(app, lifespan, registry, kernel))
    return None


async def run_shell(app: Any, lifespan: Any, registry: Registry, kernel: str) -> None:
    """Executes the database shell connection"""

    async with lifespan(app):
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


def handle_lifespan_events(
    on_startup: Optional[Sequence[Callable]] = None,
    on_shutdown: Optional[Sequence[Callable]] = None,
    lifespan: Optional[Any] = None,
) -> Any:
    """Handles with the lifespan events in the new Starlette format of lifespan.
    This adds a mask that keeps the old `on_startup` and `on_shutdown` events variable
    declaration for legacy and comprehension purposes and build the async context manager
    for the lifespan.
    """
    if lifespan:
        return lifespan
    return AyncLifespanContextManager(on_startup=on_startup, on_shutdown=on_shutdown)
