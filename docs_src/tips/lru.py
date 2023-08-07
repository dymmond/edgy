from functools import lru_cache

from esmerald.conf import settings


@lru_cache()
def get_db_connection():
    database, registry = settings.db_connection
    return database, registry
