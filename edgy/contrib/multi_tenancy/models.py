from __future__ import annotations

import uuid
import warnings
from datetime import date
from typing import Any, cast
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
    Abstract table that acts as an entry-point for managing tenants in an Edgy
    application.

    This mixin provides fields and methods for defining a tenant, including
    its schema name, domain, and various flags for automated schema management.
    Models inheriting from `TenantMixin` will represent individual tenants
    in a multi-tenant application.
    """

    schema_name: str = edgy.CharField(max_length=63, unique=True, index=True)
    domain_url: str = edgy.URLField(null=True, default=settings.domain, max_length=2048)
    tenant_name: str = edgy.CharField(max_length=100, unique=True, null=False)
    tenant_uuid: UUID = edgy.UUIDField(default=uuid.uuid4, null=False)
    paid_until: date = edgy.DateField(null=True)
    on_trial: bool = edgy.BooleanField(null=True)
    created_on: date = edgy.DateField(auto_now_add=True)

    auto_create_schema: bool = getattr(settings, "auto_create_schema", True)
    """
    Controls whether the database schema for this tenant is automatically
    created and synchronized upon saving the tenant record.

    Set this flag to `False` on a parent class if you don't want the schema
    to be automatically generated for inherited tenant models.
    """
    auto_drop_schema: bool = getattr(settings, "auto_drop_schema", False)
    """
    **Use with caution!**

    If set to `True`, the database schema associated with this tenant will be
    automatically dropped when the tenant record is deleted from this table.
    Ensure you understand the implications before enabling this flag in
    production environments.
    """

    class Meta:
        abstract = True

    def __str__(self) -> str:
        """
        Returns a string representation of the TenantMixin instance.

        Returns:
            str: A string in the format "tenant_name - schema_name".
        """
        return f"{self.tenant_name} - {self.schema_name}"

    async def real_save(
        self,
        force_insert: bool = False,
        values: dict[str, Any] | set[str] | None = None,
        force_save: bool | None = None,
    ) -> Model:
        """
        Creates or updates a tenant record and manages its associated database schema.

        When a new tenant record is saved, this method ensures the creation
        of a dedicated database schema (if `auto_create_schema` is True)
        and then migrates the tenant-specific models into that new schema.
        It prevents saving a tenant to the default or public schema.

        Args:
            force_insert (bool, optional): If `True`, forces an INSERT operation
                                           even if the record might exist.
                                           Defaults to `False`.
            values (dict[str, Any] | set[str] | None, optional): A dictionary
                                                                of values to save
                                                                or a set of
                                                                field names to save.
                                                                Defaults to `None`.
            force_save (bool | None, optional): Deprecated. Use `force_insert` instead.

        Raises:
            ModelSchemaError: If an attempt is made to save a tenant to
                              the public schema or a schema outside of its own.

        Returns:
            Model: The saved tenant model instance.
        """
        registry = self.meta.registry
        # Ensure the registry is set, as it's crucial for schema operations.
        assert registry, "registry is not set"

        # Deprecation warning for 'force_save'.
        if force_save is not None:
            warnings.warn(
                "'force_save' is deprecated in favor of 'force_insert'",
                DeprecationWarning,
                stacklevel=2,
            )
            force_insert = force_save

        # Extract database fields from the model instance.
        fields = self.extract_db_fields()
        schema_name = fields.get("schema_name", None)

        # Prevent saving to the default public schema or an existing registry schema.
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
                f"Can't update tenant outside its own schema or the public schema. "
                f"Current schema is '{current_schema}'"
            )

        # Save the tenant record using the parent's `real_save` method.
        tenant = await super().real_save(force_insert, values)
        try:
            # Attempt to create the database schema for the new tenant.
            # `if_not_exists=True` prevents errors if the schema already exists.
            # `init_tenant_models=True` ensures that tenant-specific models are
            # migrated into this new schema.
            # `update_cache=False` prevents caching issues during schema creation.
            await registry.schema.create_schema(
                schema=tenant.schema_name,
                if_not_exists=True,
                init_tenant_models=True,
                update_cache=False,
            )
        except Exception as e:
            # If schema creation fails, log the error and roll back by deleting the tenant record.
            message = f"Rolling back... {str(e)}"
            logger.error(message)
            await self.delete()
        return tenant

    async def delete(self, force_drop: bool = False) -> None:
        """
        Deletes a tenant record and, if `auto_drop_schema` is True,
        also drops its associated database schema.

        This method includes a safeguard to prevent accidental deletion
        of the default public schema.

        Args:
            force_drop (bool, optional): If `True`, forces the schema to be
                                         dropped regardless of `auto_drop_schema`.
                                         Defaults to `False`.

        Raises:
            ValueError: If an attempt is made to drop the public schema.
        """
        # Prevent deletion of the default public schema.
        if self.schema_name == settings.tenant_schema_default:
            raise ValueError("Cannot drop public schema.")

        registry = self.meta.registry
        # Ensure the registry is set.
        assert registry, "registry is not set"

        # Drop the associated database schema.
        # `cascade=True` ensures all objects within the schema are also dropped.
        # `if_exists=True` prevents errors if the schema does not exist.
        await registry.schema.drop_schema(schema=self.schema_name, cascade=True, if_exists=True)
        # Call the parent's delete method to remove the tenant record from the database.
        await super().delete()


class DomainMixin(edgy.Model):
    """
    All models that store domain information for tenants must inherit from this mixin.

    This mixin provides fields for the domain string, a foreign key to the
    tenant model, and a flag to designate a primary domain for a tenant.
    It includes custom save logic to ensure only one primary domain per tenant.
    """

    domain: str = edgy.CharField(max_length=253, unique=True, db_index=True)
    tenant: Any = edgy.ForeignKey(settings.tenant_model, index=True, related_name="domains")
    is_primary: bool = edgy.BooleanField(default=True, index=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        """
        Returns the domain string as the string representation of the instance.

        Returns:
            str: The domain string.
        """
        return self.domain

    async def real_save(
        self: Any,
        force_insert: bool = False,
        values: dict[str, Any] | set[str] | None = None,
        force_save: bool | None = None,
    ) -> Model:
        """
        Creates or updates a domain record, ensuring proper handling of the
        `is_primary` flag.

        This method ensures that for a given tenant, only one domain is marked
        as `is_primary=True`. If a new domain is set as primary, any existing
        primary domain for that tenant will be automatically set to `False`.

        Args:
            force_insert (bool, optional): If `True`, forces an INSERT operation
                                           even if the record might exist.
                                           Defaults to `False`.
            values (dict[str, Any] | set[str] | None, optional): A dictionary
                                                                of values to save
                                                                or a set of
                                                                field names to save.
                                                                Defaults to `None`.
            force_save (bool | None, optional): Deprecated. Use `force_insert` instead.

        Returns:
            Model: The saved domain model instance.
        """
        # Deprecation warning for 'force_save'.
        if force_save is not None:
            force_insert = force_save

        # Ensure a database connection is established before proceeding.
        check_db_connection(self.database)

        # Start a database transaction to ensure atomicity of the operation.
        async with self.database as database, database.transaction():
            # Query for existing primary domains associated with the current tenant,
            # excluding the current domain if it already has a primary key.
            domains = (
                type(self).query.filter(tenant=self.tenant, is_primary=True).exclude(pk=self.pk)
            )

            # Check if any primary domains already exist for this tenant.
            exists = await domains.exists()

            # Set `is_primary` for the current domain:
            # - If `self.is_primary` is already True, keep it True.
            # - Otherwise, if no other primary domains exist for this tenant,
            #   set this one as primary.
            self.is_primary = self.is_primary or (not exists)
            if self.is_primary:
                # If the current domain is or becomes primary, update all other
                # primary domains for this tenant to be non-primary.
                await domains.update(is_primary=False)

            # Call the parent's `real_save` method to persist the domain record.
            return await super().real_save(force_insert, values)

    async def delete(self) -> None:
        """
        Deletes a domain record, with a safeguard to prevent accidental
        deletion of the public domain.

        Raises:
            ValueError: If an attempt is made to delete the public domain.
        """
        # Load the associated tenant to check its schema name.
        tenant = await self.tenant.load()

        # Prevent deletion of the default public domain.
        if (
            tenant.schema_name.lower() == settings.tenant_schema_default.lower()
            and self.domain == settings.domain_name
        ):
            raise ValueError("Cannot drop public domain.")

        # Call the parent's delete method to remove the domain record.
        return await super().delete()


class TenantUserMixin(edgy.Model):
    """
    A mapping table between a user and a tenant (client).

    This mixin facilitates associating users with specific tenants in a
    multi-tenant environment. It includes fields for linking to user and
    tenant models, and a flag to indicate if a user's association with
    a tenant is active.
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
    async def get_active_user_tenant(cls, user: edgy.Model) -> edgy.Model | None:
        """
        Retrieves the active tenant associated with a given user.

        This class method queries the `TenantUserMixin` table to find
        the tenant where the user is marked as `is_active=True`.

        Args:
            user (edgy.Model): The user instance for whom to retrieve the active tenant.

        Returns:
            edgy.Model | None: The active tenant model instance if found, otherwise `None`.
        """
        registry = cls.meta.registry
        # Ensure the registry is set.
        assert registry, "registry is not set"

        try:
            # Get the model dynamically from the registry using its name.
            # Query for a tenant user record that is active and linked to the provided user.
            tenant_user_mapping = await get_model(
                registry=registry, model_name=cls.__name__
            ).query.get(user=user, is_active=True)
            # Load the actual tenant instance associated with the mapping.
            await tenant_user_mapping.tenant.load()

        except ObjectNotFound:
            # If no active tenant user mapping is found, return None.
            return None
        # Return the loaded tenant model instance.
        return cast(edgy.Model, tenant_user_mapping.tenant)

    def __str__(self) -> str:
        """
        Returns a string representation of the TenantUserMixin instance.

        Returns:
            str: A string in the format "User: user_pk, Tenant: tenant_name".
        """
        return f"User: {self.user.pk}, Tenant: {self.tenant}"

    async def real_save(self, *args: Any, **kwargs: Any) -> edgy.Model:
        """
        Creates or updates a tenant user mapping, ensuring that only one
        mapping for a given user is `is_active=True`.

        If the current mapping is set to `is_active=True`, all other active
        mappings for the same user will be automatically set to `is_active=False`.

        Args:
            *args (Any): Positional arguments passed to the parent's `real_save` method.
            **kwargs (Any): Keyword arguments passed to the parent's `real_save` method.

        Returns:
            edgy.Model: The saved tenant user mapping instance.
        """
        registry = self.meta.registry
        # Ensure the registry is set.
        assert registry, "registry is not set"

        # Call the parent's `real_save` method to persist the current record.
        await super().real_save(*args, **kwargs)

        # If the current mapping is set to active, deactivate all other active
        # mappings for the same user.
        if self.is_active:
            # Get the model dynamically from the registry using its type name.
            # Filter for active mappings for the same user, excluding the current one.
            # Update these mappings to set `is_active` to False.
            await (
                get_model(registry=registry, model_name=type(self).__name__)
                .query.filter(is_active=True, user=self.user)
                .exclude(pk=self.pk)
                .update(is_active=False)
            )
        return self
