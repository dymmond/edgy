#!/usr/bin/env python
"""
Generated by 'esmerald-admin createproject'
"""

import os
import sys

from esmerald import Esmerald, Include
from edgy import Instance, monkay
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
    This is optional. The function is only used for organisation purposes.
    """
    build_path()
    registry = get_db_connection()

    app = registry.asgi(
        Esmerald(
            routes=[Include(namespace="my_project.urls")],
        )
    )

    monkay.set_instance(Instance(app=app, registry=registry))
    return app


app = get_application()
