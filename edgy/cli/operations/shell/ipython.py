import asyncio
import sys
import typing

from monkay.asgi import Lifespan
from sayer import error

from edgy import Registry
from edgy.cli.operations.shell.utils import import_objects
from edgy.conf import settings


def get_ipython(app: typing.Any, registry: Registry, options: typing.Any = None) -> typing.Any:
    """Gets the IPython shell.

    Loads the initial configurations from the main Edgy settings
    and boots up the kernel.
    """
    try:
        from IPython import start_ipython  # pyright: ignore[reportMissingModuleSource]
        from IPython.core.async_helpers import (
            get_asyncio_loop,  # pyright: ignore[reportMissingModuleSource]
        )

        def run_ipython() -> None:
            ipython_arguments = getattr(settings, "ipython_args", [])
            loop: asyncio.BaseEventLoop = get_asyncio_loop()  # type: ignore
            ctx = None if app is None else Lifespan(app)
            if ctx is not None:
                loop.run_until_complete(ctx.__aenter__())
            try:
                with registry.with_async_env(loop):
                    # we need an initialized registry first to detect reflected models
                    imported_objects: dict[str, typing.Any] = import_objects(app, registry)
                    start_ipython(argv=ipython_arguments, user_ns=imported_objects)  # type: ignore
            finally:
                if ctx is not None:
                    loop.run_until_complete(ctx.__aexit__())

    except ImportError:
        error("You must have IPython installed to run this. Run `pip install ipython`.")
        sys.exit(1)

    return run_ipython
