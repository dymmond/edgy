from __future__ import annotations

from typing import Any

import click

import edgy
from edgy.conf import settings


@click.option(
    "-p",
    "--port",
    type=int,
    default=8000,
    help="Port to run the development server.",
    show_default=True,
)
@click.option(
    "--host",
    type=str,
    default="localhost",
    help="Server host. Typically localhost.",
    show_default=True,
)
@click.option(
    "--debug",
    default=True,
    help="Start the application in debug mode.",
    show_default=True,
    is_flag=True,
)
@click.option(
    "--log-level",
    type=str,
    default="debug",
    help="What log level should uvicorn run.",
    show_default=True,
)
@click.command(name="runserver")
def admin_serve(
    port: int,
    host: str,
    debug: bool,
    log_level: str,
) -> None:
    """Starts the Edgy admin development server.

    The --app can be passed in the form of <module>.<submodule>:<app> or be set
    as environment variable LILYA_DEFAULT_APP.

    Alternatively, if none is passed, Lilya will perform the application discovery.

    It is strongly advised not to run this command in any pther environment but developmentyping.
    This was designed to facilitate the development environment and should not be used in pr

    How to run: `edgy admin_serve`
    """

    try:
        from lilya.apps import Lilya
        from lilya.middleware.base import DefineMiddleware
        from lilya.middleware.cors import CORSMiddleware
        from lilya.routing import Include
    except ImportError:
        raise RuntimeError("Lilya needs to be installed to run admin_serve.") from None
    try:
        import jinja2  # noqa
    except ImportError:
        raise RuntimeError("Jinja2 needs to be installed to run admin_serve.") from None
    try:
        import uvicorn
    except ImportError:
        raise RuntimeError("Uvicorn needs to be installed to run admin_serve.") from None

    old_instance = edgy.monkay.instance

    if old_instance is None:
        raise RuntimeError(
            'You need to specify an app which registry is used. For experimenting use: "tests.cli.main"'
        )
    from edgy.contrib.admin.application import app as admin_app

    routes = [
        Include(
            path=settings.admin_config.admin_prefix_url,
            app=admin_app,
            middleware=[
                DefineMiddleware(
                    CORSMiddleware,
                    allow_origins=["*"],
                    allow_methods=["*"],
                    allow_headers=["*"],
                    allow_credentials=True,
                )
            ],
        ),
    ]
    if old_instance.app is not None:
        routes.append(Include(path="/", app=old_instance.app))
    app: Any = Lilya(routes=routes)
    if debug:
        app.debug = debug
    app = old_instance.registry.asgi(app)
    edgy.monkay.set_instance(edgy.Instance(registry=old_instance.registry, app=app))

    uvicorn.run(
        app=app,
        port=port,
        host=host,
        reload=False,
        lifespan="on",
        log_level=log_level,
    )
