from __future__ import annotations

from typing import Any

import click
from lilya.apps import Lilya
from lilya.cli.exceptions import DirectiveError
from lilya.middleware.base import DefineMiddleware
from lilya.middleware.cors import CORSMiddleware
from lilya.routing import Include

import edgy
from edgy.contrib.admin.application import app as admin_app


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
        import uvicorn
    except ImportError:
        raise DirectiveError(detail="Uvicorn needs to be installed to run Lilya.") from None

    old_instance = edgy.monkay.instance

    if old_instance is None:
        raise DirectiveError(
            detail='You need to specify an app which registry is used. For experimenting use: "tests.cli.main"'
        )

    app: Any = Lilya(
        routes=[Include(path="/", app=admin_app)],
        middleware=[
            DefineMiddleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
                allow_credentials=True,
            )
        ],
    )
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
