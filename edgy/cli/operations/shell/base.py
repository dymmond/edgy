from __future__ import annotations

import asyncio
from contextlib import nullcontext
from typing import Annotated

import click
from monkay.asgi import Lifespan
from sayer import Option, command

import edgy
from edgy.cli.operations.shell.enums import ShellOption


@command
async def shell(
    kernel: Annotated[
        str,
        Option(
            default="ipython",
            type=click.Choice(f.value for f in ShellOption.__members__.values()),
            help="Which shell should start.",
            show_default=True,
        ),
    ],
) -> None:
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

    assert registry is not None
    async with nullcontext() if app is None else Lifespan(app):
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

    return None
