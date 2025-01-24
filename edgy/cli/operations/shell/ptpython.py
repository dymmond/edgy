import os
import sys
import typing

from edgy import Registry
from edgy.cli.operations.shell.utils import import_objects
from edgy.conf import settings
from edgy.core.terminal import Print

printer = Print()


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

        def run_ptpython() -> None:
            history_filename = os.path.expanduser("~/.ptpython_history")

            config_file = os.path.expanduser(settings.ptpython_config_file)
            with registry.with_async_env():
                # we need an initialized registry first to detect reflected models
                imported_objects = import_objects(app, registry)
                if not os.path.exists(config_file):
                    embed(
                        globals=imported_objects,
                        history_filename=history_filename,
                        vi_mode=vi_mode(),
                    )
                else:
                    embed(
                        globals=imported_objects,
                        history_filename=history_filename,
                        vi_mode=vi_mode(),
                        configure=run_config,
                    )

    except (ModuleNotFoundError, ImportError):
        error = "You must have ptpython installed to run this. Run `pip install ptpython`"
        printer.write_error(error)
        sys.exit(1)

    return run_ptpython
