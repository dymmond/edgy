from __future__ import annotations

import os
import re
from functools import cached_property
from pathlib import Path

from monkay import ExtensionProtocol
from pydantic_settings import BaseSettings, SettingsConfigDict

from edgy.contrib.admin.config import AdminConfig


class MediaSettings(BaseSettings):
    """
    All settings related to media and media root.
    """

    file_upload_temp_dir: str | None = None
    file_upload_permissions: int | None = 0o644
    file_upload_directory_permissions: int | None = None

    # Don't allow overwriting the project files by default, set to media
    media_root: str | os.PathLike = Path("media/")
    media_url: str = ""

    # Storage defaults
    storages: dict[str, dict] = {
        "default": {
            "backend": "edgy.core.files.storage.filesystem.FileSystemStorage",
        },
    }


class MigrationSettings(BaseSettings):
    allow_automigrations: bool = True
    multi_schema: bool | re.Pattern | str = False
    ignore_schema_pattern: None | re.Pattern | str = "information_schema"
    migrate_databases: list[str | None] | tuple[str | None, ...] = (None,)
    migration_directory: str | os.PathLike = Path("migrations/")

    # Extra keyword arguments to pass to alembic
    alembic_ctx_kwargs: dict = {
        "compare_type": True,
        "render_as_batch": True,
    }


class EdgySettings(MediaSettings, MigrationSettings):
    model_config = SettingsConfigDict(extra="allow", ignored_types=(cached_property,))
    allow_auto_compute_server_defaults: bool = True
    preloads: list[str] | tuple[str, ...] = ()
    extensions: list[ExtensionProtocol] | tuple[ExtensionProtocol, ...] = ()
    ipython_args: list[str] | tuple[str, ...] = ("--no-banner",)
    ptpython_config_file: str = "~/.config/ptpython/config.py"

    @cached_property
    def admin_config(self) -> AdminConfig:
        return AdminConfig()
