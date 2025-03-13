from typing import Any
import logging

import edgy
from edgy.contrib.permissions import BasePermission
from sqlalchemy.exc import IntegrityError

# Import the User model from your app
from accounts.models import User

logger = logging.getLogger(__name__)

registry = edgy.Registry("sqlite:///foo.sqlite3")


class Group(edgy.Model):
    name = edgy.fields.CharField(max_length=100)
    users = edgy.fields.ManyToMany("User", through_tablename=edgy.NEW_M2M_NAMING)

    class Meta:
        registry = registry


class Permission(BasePermission):
    users: list["User"] = edgy.ManyToManyField(
        "User", related_name="permissions", through_tablename=edgy.NEW_M2M_NAMING
    )
    groups: list["Group"] = edgy.ManyToManyField(
        "Group", related_name="permissions", through_tablename=edgy.NEW_M2M_NAMING
    )
    name_model: str = edgy.fields.CharField(max_length=100, null=True)
    obj = edgy.fields.ForeignKey("ContentType", null=True)

    class Meta:
        registry = registry
        unique_together = [("name", "name_model", "obj")]

    @classmethod
    async def __bulk_create_or_update_permissions(
        cls, users: list["User"], obj: edgy.Model, names: list[str], revoke: bool
    ) -> None:
        """
        Creates or updates a list of permissions for the given users and object.
        """
        if not revoke:
            permissions = [{"users": users, "obj": obj, "name": name} for name in names]
            try:
                await cls.query.bulk_create(permissions)
            except IntegrityError as e:
                logger.error("Error creating permissions", error=str(e))
            return None

        await cls.query.filter(users__in=users, obj=obj, name__in=names).delete()

    @classmethod
    async def __assign_permission(
        cls, users: list["User"], obj: edgy.Model, name: str, revoke: bool
    ) -> None:
        """
        Creates a permission for the given users and object.
        """
        if not revoke:
            try:
                await cls.query.create(users=users, obj=obj, name=name)
            except IntegrityError as e:
                logger.error("Error creating permission", error=str(e))
            return None

        await cls.query.filter(users__in=users, obj=obj, name=name).delete()

    @classmethod
    async def assign_permission(
        cls,
        users: list["User"] | Any,
        obj: edgy.Model,
        name: str | None = None,
        revoke: bool = False,
        bulk_create_or_update: bool = False,
        names: list[str] | None = None,
    ) -> None:
        """
        Assign or revoke permissions for a user or a list of users on a given object.

        Args:
            users (list["User"] | "User"): A user or a list of users to whom the permission will be assigned or revoked.
            obj (edgy.Model): The object on which the permission will be assigned or revoked.
            name (str | None, optional): The name of the permission to be assigned or revoked. Defaults to None.
            revoke (bool, optional): If True, the permission will be revoked. If False, the permission will be assigned. Defaults to False.
            bulk_create_or_update (bool, optional): If True, permissions will be created or updated in bulk. Defaults to False.
            names (list[str] | None, optional): A list of permission names to be created or updated in bulk. Required if bulk_create_or_update is True. Defaults to None.
        Raises:
            AssertionError: If users is not a list or a User instance.
            ValueError: If bulk_create_or_update is True and names is not provided.
        Returns:
            None
        """

        assert isinstance(users, list) or isinstance(users, User), (
            "Users must be a list or a User instance."
        )

        if not isinstance(users, list):
            users = [users]

        if bulk_create_or_update and not names:
            raise ValueError(
                "You must provide a list of names to create or update permissions in bulk.",
            )
        elif bulk_create_or_update:
            return await cls.__bulk_create_or_update_permissions(users, obj, names, revoke)

        return await cls.__assign_permission(users, obj, name, revoke)
