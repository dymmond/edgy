from __future__ import annotations

import os
import sys
from contextlib import suppress
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import click
from sayer import error
from sayer.core.groups.sayer import SayerGroup

from .constants import COMMANDS_WITHOUT_APP, DISCOVERY_PRELOADS, EXCLUDED_DIRECTIVES


class DirectiveGroup(SayerGroup):
    """Custom directive group to handle with the context and directives commands"""

    def use_app_or_path_from_ctx(self, ctx: click.Context) -> None:
        app = ctx.params.get("app", None)
        if app is None and "--app" in EXCLUDED_DIRECTIVES:
            return
        path = ctx.params.get("path", None)
        if path is None and "--path" in EXCLUDED_DIRECTIVES:
            return

        if "--help" not in ctx.args:
            cwd = Path.cwd() if path is None else Path(path)
            sys.path.insert(0, str(cwd))
            import edgy

            # try to initialize the config and load preloads if the config is ready
            edgy.monkay.evaluate_settings()
            if ctx.invoked_subcommand not in COMMANDS_WITHOUT_APP:
                if app:
                    import_module(app)
                    if edgy.monkay.instance is None:
                        error(f'Edgy instance still unset after importing "{app}"')
                        sys.exit(1)
                elif edgy.monkay.instance is None:
                    # skip when already set by a module preloaded
                    found: bool = False
                    env_var = os.environ.get("EDGY_DEFAULT_APP")
                    if env_var:
                        with suppress(ImportError):
                            import_module(env_var)
                        if cast(Any, edgy.monkay.instance) is not None:
                            error(
                                f'Edgy instance still unset after importing "{env_var}" (EDGY_DEFAULT_APP).'
                            )
                            sys.exit(1)

                    for preload in DISCOVERY_PRELOADS:
                        with suppress(ImportError):
                            import_module(preload)
                        if cast(Any, edgy.monkay.instance) is not None:
                            found = True
                    if not found:
                        for path in cwd.iterdir():
                            if "." not in path.name and path.is_dir():
                                for preload in DISCOVERY_PRELOADS:
                                    with suppress(ImportError):
                                        import_module(f"{path.name}.{preload}")
                                    if cast(Any, edgy.monkay.instance is not None):
                                        found = True
                                        break
                    if not found:
                        error("Could not find edgy application via autodiscovery.")
                        sys.exit(1)

    def invoke(self, ctx: click.Context) -> Any:
        """
        Directives can be ignored depending of the functionality from what is being
        called.
        """
        self.use_app_or_path_from_ctx(ctx)

        return super().invoke(ctx)
