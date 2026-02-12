#!/usr/bin/env python

import os
import sys

from ravyn import Ravyn, Include
from my_project.utils import get_db_connection


def build_path():
    """
    Builds the path of the project and project root.
    """
    SITE_ROOT = os.path.dirname(os.path.realpath(__file__))

    if SITE_ROOT not in sys.path:
        sys.path.append(SITE_ROOT)
        # in case of an application model with apps
        sys.path.append(os.path.join(SITE_ROOT, "apps"))


def get_application():
    """
    Encapsulating in methods can be useful for controlling the import order but is optional.
    """
    # first call build_path
    build_path()
    # because edgy tries to load settings eagerly
    from edgy import monkay, Instance

    registry = get_db_connection()
    # ensure the settings are loaded
    monkay.evaluate_settings(ignore_import_errors=False)

    app = registry.asgi(
        Ravyn(
            routes=[Include(namespace="my_project.urls")],
        )
    )

    monkay.set_instance(Instance(app=app, registry=registry))
    return app


app = get_application()
