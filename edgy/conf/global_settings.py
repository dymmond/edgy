from functools import cached_property
from typing import Any, Dict, List, Set, Union

from pydantic_settings import BaseSettings, SettingsConfigDict


class MediaSettings(BaseSettings):
    """
    All settings related to media and media root.
    """

    file_upload_temp_dir: Union[str, None] = None
    file_upload_permissions: Union[str, Any] = 0o644
    file_upload_directory_permissions: Union[str, None] = None
    media_root: str = ""
    media_url: str = ""

    # Storage defaults
    storages = {
        "default": {
            "backend": "edgy.core.files.storage.FileSystemStorage",
        },
        # "staticfiles": {
        #     "storage": "django.contrib.staticfiles.storage.StaticFilesStorage",
        # },
    }


class EdgySettings(MediaSettings):
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
    default_related_lookup_field: str = "id"
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
