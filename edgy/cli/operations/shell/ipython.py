import sys
import typing

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

        def run_ipython() -> None:
            ipython_arguments = getattr(settings, "ipython_args", [])
            with registry.with_async_env():
                # we need an initialized registry first to detect reflected models
                imported_objects: dict[str, typing.Any] = import_objects(app, registry)
                start_ipython(argv=ipython_arguments, user_ns=imported_objects)  # type: ignore

    except ImportError:
        error("You must have IPython installed to run this. Run `pip install ipython`.")
        sys.exit(1)

    return run_ipython
