#!/usr/bin/env python
import os
import sys
from pathlib import Path

from my_project.utils import get_db_connection

from esmerald import Esmerald, Include


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
    Encapsulate in methods can be useful for capsulating and delaying imports but is optional.
    """
    # first call build_path
    build_path()
    # because edgy tries to load settings eagerly

    registry = get_db_connection()

    app = registry.asgi(
        Esmerald(
            routes=[Include(namespace="my_project.urls")],
        )
    )

    monkay.set_instance(Instance(registry=registry, app=app))
    return app


app = get_application()
