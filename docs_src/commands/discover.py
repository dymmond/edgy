#!/usr/bin/env python
import os
import sys
from pathlib import Path

from esmerald import Esmerald, Include
from my_project.utils import get_db_connection


def build_path():
    """
    Builds the path of the project and project root.
    """
    Path(__file__).resolve().parent.parent
    SITE_ROOT = os.path.dirname(os.path.realpath(__file__))

    if SITE_ROOT not in sys.path:
        sys.path.append(SITE_ROOT)
        sys.path.append(os.path.join(SITE_ROOT, "apps"))


def get_application():
    """
    Encapsulating in methods can be useful for controlling the import order but is optional.
    """
    from edgy import Instance, monkay

    build_path()
    registry = get_db_connection()

    app = registry.asgi(
        Esmerald(
            routes=[Include(namespace="my_project.urls")],
        )
    )

    monkay.set_instance(Instance(registry=registry, app=app))
    return app


app = get_application()
