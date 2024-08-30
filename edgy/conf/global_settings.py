import os
from functools import cached_property
from pathlib import Path
from typing import Any, Dict, List, Union

from pydantic_settings import BaseSettings, SettingsConfigDict


class MediaSettings(BaseSettings):
    """
    All settings related to media and media root.
    """

    file_upload_temp_dir: Union[str, None] = None
    file_upload_permissions: Union[str, Any] = 0o644
    file_upload_directory_permissions: Union[str, None] = None
    # don't allow overwriting the project files by default, set to media
    media_root: Union[str, os.PathLike] = Path("media/")
    media_url: str = ""

    # Storage defaults
    storages: Dict[str, dict] = {
        "default": {
            "backend": "edgy.core.files.storage.filesystem.FileSystemStorage",
        },
        # "staticfiles": {
        #     "storage": "django.contrib.staticfiles.storage.StaticFilesStorage",
        # },
    }


class EdgySettings(MediaSettings):
    model_config = SettingsConfigDict(extra="allow", ignored_types=(cached_property,))
    ipython_args: List[str] = ["--no-banner"]
    ptpython_config_file: str = "~/.config/ptpython/config.py"

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
