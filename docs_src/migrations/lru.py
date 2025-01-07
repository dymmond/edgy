from functools import lru_cache


@lru_cache()
def get_db_connection():
    from edgy import Registry

    # use echo=True for getting the connection infos printed, extra kwargs are passed to main database
    return Registry("postgresql+asyncpg://user:pass@localhost:5432/my_database", echo=True)
