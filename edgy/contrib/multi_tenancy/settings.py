from __future__ import annotations

import os
from functools import cached_property
from typing import Any

from pydantic_settings import SettingsConfigDict

from edgy.conf.global_settings import EdgySettings


class TenancySettings(EdgySettings):
    """
    Configuration settings specifically designed for managing multi-tenancy
    features within an Edgy application.

    This class extends `EdgySettings` to provide a centralized place for
    defining and loading settings related to tenant schema management,
    tenant and domain model references, and default values.
    """

    model_config = SettingsConfigDict(extra="allow", ignored_types=(cached_property,))
    auto_create_schema: bool = True
    """
    A boolean flag indicating whether database schemas for new tenants
    should be automatically created when a tenant record is saved.

    Defaults to `True`.
    """
    auto_drop_schema: bool = False
    """
    A boolean flag indicating whether database schemas should be automatically
    dropped when a tenant record is deleted.

    **Use with extreme caution in production environments.** Defaults to `False`.
    """
    tenant_schema_default: str = "public"
    """
    The default schema name used for the public or main tenant.

    Defaults to "public".
    """
    tenant_model: str | None = None
    """
    A string representing the import path to the tenant model class.

    This should be in the format 'your_app.models.YourTenantModel'.
    Defaults to `None`.
    """
    domain: Any = os.getenv("DOMAIN")
    """
    The default domain associated with the application, typically read
    from the 'DOMAIN' environment variable.

    This can be used for configuring multi-tenant domain routing.
    Defaults to the value of the 'DOMAIN' environment variable.
    """
    domain_name: str = "localhost"
    """
    The name of the default domain for the application.

    Defaults to "localhost", useful for local development environments.
    """
    auth_user_model: str | None = None
    """
    A string representing the import path to the authentication user model class.

    This should be in the format 'your_app.models.YourUser'.
    Defaults to `None`.
    """
