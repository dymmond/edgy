from __future__ import annotations

import os
import re
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from monkay import ExtensionProtocol
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from edgy.contrib.admin.config import AdminConfig


class MediaSettings(BaseSettings):
    """
    Settings related to media file uploads and storage within the Edgy framework.

    This class defines configuration options for temporary file directories,
    permissions, media root, media URL, and default storage backends.
    """

    file_upload_temp_dir: str | None = None
    """
    Optional: Specifies a temporary directory for file uploads.

    If set to `None`, a default system temporary directory will be used.
    """
    file_upload_permissions: int | None = 0o644
    """
    Optional: The default permissions for uploaded files.

    Expressed as an octal integer (e.g., `0o644`). If `None`, default
    system permissions will be applied.
    """
    file_upload_directory_permissions: int | None = None
    """
    Optional: The default permissions for newly created directories during file uploads.

    Expressed as an octal integer (e.g., `0o755`). If `None`, default
    system permissions will be applied.
    """

    media_root: str | os.PathLike = Path("media/")
    """
    The absolute path to the directory where user-uploaded media files are stored.

    Defaults to a 'media/' directory within the project root.
    """
    media_url: str = ""
    """
    The base URL for serving media files.

    This URL will be prepended to the relative paths of media files when
    generating their public URLs. Defaults to an empty string.
    """

    storages: dict[str, dict] = {
        "default": {
            "backend": "edgy.core.files.storage.filesystem.FileSystemStorage",
        },
    }
    """
    A dictionary defining different storage backends available for file uploads.

    Each key represents a storage name (e.g., "default"), and its value is
    a dictionary specifying the 'backend' class path and any additional
    backend-specific configurations. The 'default' backend uses
    `FileSystemStorage`.
    """


class MigrationSettings(BaseSettings):
    """
    Settings related to database migrations within the Edgy framework.

    This class provides configurations for automatic migrations, multi-schema
    support, ignored schemas, migration directories, and Alembic context arguments.
    """

    allow_automigrations: bool = True
    """
    Boolean indicating whether automatic migrations are allowed.

    If `True`, Edgy will attempt to automatically detect and apply database
    schema changes. Defaults to `True`.
    """
    multi_schema: bool | re.Pattern | str = False
    """
    Configures multi-schema support for migrations.

    Can be `True` for general multi-schema, `False` to disable, a
    `re.Pattern` to match specific schemas, or a `str` pattern. Defaults to `False`.
    """
    ignore_schema_pattern: None | re.Pattern | str = "information_schema"
    """
    A regular expression pattern or string to ignore specific schemas during migrations.

    Schemas matching this pattern will be excluded from migration operations.
    Defaults to "information_schema".
    """
    migrate_databases: list[str | None] | tuple[str | None, ...] = (None,)
    """
    A list or tuple of database names to include in migration operations.

    If `None` is included, it implies all databases or the default database
    should be migrated. Defaults to `(None,)`.
    """
    migration_directory: str | os.PathLike = Path("migrations/")
    """
    The path to the directory where migration scripts are stored.

    Defaults to a 'migrations/' directory within the project root.
    """

    alembic_ctx_kwargs: dict = {
        "compare_type": True,
        "render_as_batch": True,
    }
    """
    Extra keyword arguments to pass to the Alembic migration context.

    These arguments control the behavior of Alembic during schema comparison
    and rendering of migration scripts. Defaults to enabling type comparison
    and batch rendering.
    """


class EdgySettings(MediaSettings, MigrationSettings):
    """
    Main settings class for the Edgy framework, inheriting from `MediaSettings`
    and `MigrationSettings`.

    This class consolidates all configurable aspects of an Edgy application,
    including general application behavior, extensions, preloads, and CLI tools.
    """

    # Pydantic-settings configuration:
    # - `extra="allow"`: Allows additional fields not explicitly defined in the settings.
    # - `ignored_types=(cached_property,)`: Prevents Pydantic from trying to validate
    #   cached properties, as they are dynamic attributes.
    model_config = SettingsConfigDict(extra="allow", ignored_types=(cached_property,))

    allow_auto_compute_server_defaults: bool = True
    """
    Boolean indicating whether server-side defaults should be automatically computed.

    If `True`, Edgy will attempt to infer and apply default values from the
    database server when not explicitly provided. Defaults to `True`.
    """
    preloads: list[str] | tuple[str, ...] = ()
    """
    A list or tuple of module paths to be preloaded at application startup.

    These modules are imported early in the application lifecycle.
    Defaults to an empty tuple.
    """
    extensions: list[ExtensionProtocol] | tuple[ExtensionProtocol, ...] = ()
    """
    A list or tuple of Monkay `ExtensionProtocol` instances to be loaded.

    These extensions provide additional functionalities and integrations to
    the Monkay-based Edgy environment. Defaults to an empty tuple.
    """
    ipython_args: list[str] | tuple[str, ...] = ("--no-banner",)
    """
    A list or tuple of arguments to pass to the IPython shell when launched via Edgy.

    Defaults to `("--no-banner",)` to suppress the IPython startup banner.
    """
    ptpython_config_file: str = "~/.config/ptpython/config.py"
    """
    The path to the ptpython configuration file.

    Defaults to `~/.config/ptpython/config.py`.
    """

    @cached_property
    def admin_config(self) -> AdminConfig:
        """
        Returns an instance of `AdminConfig`.

        This property is cached to ensure that the `AdminConfig` is
        instantiated only once per `EdgySettings` instance, providing
        efficient access to admin-related configurations.
        """
        from edgy.contrib.admin.config import AdminConfig

        return AdminConfig()
