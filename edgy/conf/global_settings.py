import os
from functools import cached_property
from pathlib import Path
from typing import Union

from pydantic_settings import BaseSettings, SettingsConfigDict


class MediaSettings(BaseSettings):
    """
    All settings related to media and media root.
    """

    file_upload_temp_dir: Union[str, None] = None
    file_upload_permissions: Union[int, None] = 0o644
    file_upload_directory_permissions: Union[int, None] = None
    # don't allow overwriting the project files by default, set to media
    media_root: Union[str, os.PathLike] = Path("media/")
    media_url: str = ""

    # Storage defaults
    storages: dict[str, dict] = {
        "default": {
            "backend": "edgy.core.files.storage.filesystem.FileSystemStorage",
        },
        # "staticfiles": {
        #     "storage": "django.contrib.staticfiles.storage.StaticFilesStorage",
        # },
    }


class EdgySettings(MediaSettings):
    model_config = SettingsConfigDict(extra="allow", ignored_types=(cached_property,))
    ipython_args: list[str] = ["--no-banner"]
    ptpython_config_file: str = "~/.config/ptpython/config.py"
