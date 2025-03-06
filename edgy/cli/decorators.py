import sys
from contextlib import suppress
from functools import wraps
from importlib import import_module
from pathlib import Path
from typing import Any, NoReturn, Optional, TypeVar

from alembic.util import CommandError
from loguru import logger

from .constants import APP_PARAMETER, COMMANDS_WITHOUT_APP, DISCOVERY_PRELOADS

T = TypeVar("T")


def catch_errors(fn: T) -> T:
    @wraps(fn)  # type: ignore
    def wrap(*args: Any, **kwargs: Any) -> NoReturn:
        try:
            fn(*args, **kwargs)  # type: ignore
        except (CommandError, RuntimeError) as exc:
            logger.error(f"Error: {str(exc)}")
            sys.exit(1)

    return wrap  # type: ignore


def add_migration_directory_option(fn: Any) -> Any:
    import click

    def callback(ctx: Any, param: str, value: Optional[str]) -> None:
        import edgy

        if value is not None:
            edgy.settings.migration_directory = value

    return click.option(
        "-d",
        "--directory",
        default=None,
        help=('Migration script directory (default is "migrations")'),
        expose_value=False,
        is_eager=True,
        callback=callback,
    )(fn)


def add_force_field_nullable_option(fn: Any) -> Any:
    import click

    return click.option(
        "--null-field",
        "--nf",
        multiple=True,
        default=(),
        help='Force field being nullable. Syntax model:field or ":field" for auto-detection of models with such a field.',
    )(fn)


def add_app_module_option(fn: Any) -> Any:
    import click

    def callback(ctx: click.Context, param: str, value: Optional[str]) -> None:
        import edgy

        # before importing anything inject the cwd
        cwd = Path.cwd()
        sys.path.insert(0, str(cwd))
        # try to initialize the config and load preloads if the config is ready
        edgy.monkay.evaluate_settings()

        if ctx.invoked_subcommand in COMMANDS_WITHOUT_APP:
            return
        if value:
            import_module(value)
            if edgy.monkay.instance is None:
                raise RuntimeError(f'Instance still unset after importing "{value}"')

        elif edgy.monkay.instance is None:
            # skip when already set by a module preloaded
            for preload in DISCOVERY_PRELOADS:
                with suppress(ImportError):
                    import_module(preload)
                if edgy.monkay.instance is not None:
                    return  # type: ignore
            for path in cwd.iterdir():
                if "." not in path.name and path.is_dir():
                    for preload in DISCOVERY_PRELOADS:
                        with suppress(ImportError):
                            import_module(f"{path.name}.{preload}")
                        if edgy.monkay.instance is not None:
                            return  # type: ignore

    return click.option(
        APP_PARAMETER,
        "path",
        help="Module path to the application to generate the migrations.",
        envvar="EDGY_DEFAULT_APP",
        default="",
        expose_value=False,
        is_eager=True,
        callback=callback,
    )(fn)
