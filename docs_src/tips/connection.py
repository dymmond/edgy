#!/usr/bin/env python

import os
import sys

from edgy import Instance, monkay
from ravyn import Ravyn, Include


def build_path():
    """
    Builds the path of the project and project root.
    """  #
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
    # import ravyn settings now
    from ravyn.conf import settings

    monkay.settings = lambda: settings.edgy_settings  # rewire the settings
    monkay.evaluate_settings(ignore_import_errors=False)  # import preloads

    # now the project is in the search path and we can import
    from my_project.utils import get_db_connection

    registry = get_db_connection()

    app = registry.asgi(
        Ravyn(
            routes=[Include(namespace="my_project.urls")],
        )
    )

    monkay.set_instance(Instance(registry=registry, app=app))
    return app


app = get_application()
