import sys
import os
from functools import lru_cache


# we need this also here because we access settings and must be sure the import path is importable
def build_path():
    """
    Builds the path of the project and project root.
    """
    SITE_ROOT = os.path.dirname(os.path.realpath(__file__))

    if SITE_ROOT not in sys.path:
        sys.path.append(SITE_ROOT)
        # in case of apps
        sys.path.append(os.path.join(SITE_ROOT, "apps"))


@lru_cache()
def get_db_connection():
    from esmerald.conf import settings

    return settings.db_connection
