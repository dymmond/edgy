from functools import lru_cache

from esmerald.conf import settings


@lru_cache()
def get_db_connection():
    return settings.db_connection
