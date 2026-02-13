from functools import lru_cache


@lru_cache()
def get_db_connection():
    # Encapsulate to delay the import
    from ravyn.conf import settings

    return settings.db_connection
