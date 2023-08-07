from functools import lru_cache

from saffier import Database, Registry


@lru_cache()
def get_db_connection():
    database = Database("postgresql+asyncpg://user:pass@localhost:5432/my_database")
    return database, Registry(database=database)
