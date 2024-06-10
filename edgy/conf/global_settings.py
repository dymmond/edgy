from functools import cached_property
from typing import Dict, List, Set

from pydantic_settings import BaseSettings, SettingsConfigDict


class EdgySettings(BaseSettings):
    model_config = SettingsConfigDict(extra="allow", ignored_types=(cached_property,))
    ipython_args: List[str] = ["--no-banner"]
    ptpython_config_file: str = "~/.config/ptpython/config.py"

    # Dialects
    postgres_dialects: Set[str] = {"postgres", "postgresql"}
    mysql_dialects: Set[str] = {"mysql"}
    sqlite_dialects: Set[str] = {"sqlite"}
    mssql_dialects: Set[str] = {"mssql"}

    # Drivers
    postgres_drivers: Set[str] = {"aiopg", "asyncpg"}
    mysql_drivers: Set[str] = {"aiomysql", "asyncmy"}
    sqlite_drivers: Set[str] = {"aiosqlite"}

    @property
    def mssql_drivers(self) -> Set[str]:
        """
        Do not override this one as SQLAlchemy doesn't support async for MSSQL.
        """
        return {"aioodbc"}

    # General settings
    filter_operators: Dict[str, str] = {
        "exact": "__eq__",
        "iexact": "ilike",
        "contains": "like",
        "icontains": "ilike",
        "in": "in_",
        "gt": "__gt__",
        "gte": "__ge__",
        "lt": "__lt__",
        "lte": "__le__",
    }
    many_to_many_relation: str = "relation_{key}"
    dialects: Dict[str, str] = {"postgres": "postgres", "postgresql": "postgresql"}
