from functools import lru_cache

from edgy import Database, Registry


@lru_cache()
def get_db_connection():
    # use echo=True for getting the connection infos printed
    database = Database("postgresql+asyncpg://user:pass@localhost:5432/my_database", echo=True)
    return Registry(database=database)
