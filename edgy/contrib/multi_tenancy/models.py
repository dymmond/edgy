import uuid
import warnings
from datetime import date
from typing import Any, Optional, Union, cast
from uuid import UUID

from loguru import logger

import edgy
from edgy import settings
from edgy.core.db.models.model import Model
from edgy.core.db.models.utils import get_model
from edgy.core.utils.db import check_db_connection
from edgy.exceptions import ModelSchemaError, ObjectNotFound


class TenantMixin(edgy.Model):
    """
    Abstract table that acts as an entry-point for
    the tenants with Edgy contrib.
    """

    schema_name: str = edgy.CharField(max_length=63, unique=True, index=True)
    domain_url: str = edgy.URLField(null=True, default=settings.domain, max_length=2048)
    tenant_name: str = edgy.CharField(max_length=100, unique=True, null=False)
    tenant_uuid: UUID = edgy.UUIDField(default=uuid.uuid4, null=False)
    paid_until: date = edgy.DateField(null=True)
    on_trial: bool = edgy.BooleanField(null=True)
    created_on: date = edgy.DateField(auto_now_add=True)

    # Default True, the schema will be automatically created and synched when it is saved.
    auto_create_schema: bool = getattr(settings, "auto_create_schema", True)
    """
    Set this flag to false on a parent class if you don't want the schema to be automatically
    generated.
    """
    auto_drop_schema: bool = getattr(settings, "auto_drop_schema", False)
    """
    Use with caution! Set this flag to true if you want the schema to be dropped if the
    tenant row is deleted from this table.
    """

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.tenant_name} - {self.schema_name}"

    async def save(
        self,
        force_insert: bool = False,
        values: Union[dict[str, Any], set[str], None] = None,
        force_save: Optional[bool] = None,
    ) -> Model:
        """
        Creates a tenant record and generates a schema in the database.

        When a schema is created, then generates the tables for that same schema
        from the tenant models.
        """
        registry = self.meta.registry
        assert registry, "registry is not set"
        if force_save is not None:
            warnings.warn(
                "'force_save' is deprecated in favor of 'force_insert'",
                DeprecationWarning,
                stacklevel=2,
            )
            force_insert = force_save
        fields = self.extract_db_fields()
        schema_name = fields.get("schema_name", None)

        if (
            not schema_name
            or schema_name.lower() == settings.tenant_schema_default.lower()
            or schema_name == registry.db_schema
        ):
            current_schema = (
                settings.tenant_schema_default.lower()
                if not registry.db_schema
                else registry.db_schema
            )
            raise ModelSchemaError(
                f"Can't update tenant outside it's own schema or the public schema. Current schema is '{current_schema}'"
            )

        tenant = await super().save(force_insert, values)
        try:
            await registry.schema.create_schema(
                schema=tenant.schema_name,
                if_not_exists=True,
                init_tenant_models=True,
                update_cache=False,
            )
        except Exception as e:
            message = f"Rolling back... {str(e)}"
            logger.error(message)
            await self.delete()
        return tenant

    async def delete(self, force_drop: bool = False) -> None:
        """
        Validates the permissions for the schema before deleting it.
        """
        if self.schema_name == settings.tenant_schema_default:
            raise ValueError("Cannot drop public schema.")
        registry = self.meta.registry
        assert registry, "registry is not set"

        await registry.schema.drop_schema(schema=self.schema_name, cascade=True, if_exists=True)
        await super().delete()


class DomainMixin(edgy.Model):
    """
    All models that store the domains must use this class
    """

    domain: str = edgy.CharField(max_length=253, unique=True, db_index=True)
    tenant: Any = edgy.ForeignKey(settings.tenant_model, index=True, related_name="domains")
    is_primary: bool = edgy.BooleanField(default=True, index=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.domain

    async def save(
        self: Any,
        force_insert: bool = False,
        values: Union[dict[str, Any], set[str], None] = None,
        force_save: Optional[bool] = None,
    ) -> Model:
        if force_save is not None:
            force_insert = force_save
        check_db_connection(self.database)
        async with self.database as database, database.transaction():
            domains = (
                type(self).query.filter(tenant=self.tenant, is_primary=True).exclude(pk=self.pk)
            )

            exists = await domains.exists()

            self.is_primary = self.is_primary or (not exists)
            if self.is_primary:
                await domains.update(is_primary=False)

            return await super().save(force_insert, values)

    async def delete(self) -> None:
        tenant = await self.tenant.load()
        if (
            tenant.schema_name.lower() == settings.tenant_schema_default.lower()
            and self.domain == settings.domain_name
        ):
            raise ValueError("Cannot drop public domain.")
        return await super().delete()


class TenantUserMixin(edgy.Model):
    """
    Mapping between user and a client (tenant).
    """

    user: Any = edgy.ForeignKey(
        settings.auth_user_model,
        null=False,
        related_name="tenant_user_users",
    )
    tenant: Any = edgy.ForeignKey(
        settings.tenant_model,
        null=False,
        related_name="tenant_users_tenant",
    )
    is_active: bool = edgy.BooleanField(default=False)
    created_on: date = edgy.DateField(auto_now_add=True)

    class Meta:
        abstract = True

    @classmethod
    async def get_active_user_tenant(cls, user: edgy.Model) -> Union[edgy.Model, None]:
        """
        Obtains the active user tenant.
        """
        registry = cls.meta.registry
        assert registry, "registry is not set"
        try:
            tenant = await get_model(registry=registry, model_name=cls.__name__).query.get(
                user=user, is_active=True
            )
            await tenant.tenant.load()

        except ObjectNotFound:
            return None
        return cast(edgy.Model, tenant.tenant)

    def __str__(self) -> str:
        return f"User: {self.user.pk}, Tenant: {self.tenant}"

    async def save(self, *args: Any, **kwargs: Any) -> edgy.Model:
        registry = self.meta.registry
        assert registry, "registry is not set"
        await super().save(*args, **kwargs)
        if self.is_active:
            await (
                get_model(registry=registry, model_name=type(self).__name__)
                .query.filter(is_active=True, user=self.user)
                .exclude(pk=self.pk)
                .update(is_active=False)
            )
        return self
