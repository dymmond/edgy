import os
import sys
import typing
from contextlib import nullcontext

from monkay.asgi import Lifespan
from sayer import error

from edgy import Registry
from edgy.cli.operations.shell.utils import import_objects
from edgy.conf import settings


def vi_mode() -> typing.Any:
    editor = os.environ.get("EDITOR")
    if not editor:
        return False
    editor = os.path.basename(editor)
    return editor.startswith("vi") or editor.endswith("vim")


def get_ptpython(app: typing.Any, registry: Registry, options: typing.Any = None) -> typing.Any:
    """Gets the PTPython shell.

    Loads the initial configurations from the main Edgy settings
    and boots up the kernel.
    """
    try:
        from ptpython.repl import embed, run_config

        async def run_ptpython() -> None:
            history_filename = os.path.expanduser("~/.ptpython_history")

            config_file = os.path.expanduser(settings.ptpython_config_file)
            ctx = nullcontext() if app is None else Lifespan(app)
            async with ctx, registry:
                # we need an initialized registry first to detect reflected models
                imported_objects = import_objects(app, registry)
                await embed(
                    globals=imported_objects,
                    history_filename=history_filename,
                    vi_mode=vi_mode(),
                    configure=run_config if os.path.exists(config_file) else None,
                    return_asyncio_coroutine=True,
                )

    except ImportError:
        error("You must have ptpython installed to run this. Run `pip install ptpython`.")
        sys.exit(1)

    return run_ptpython
