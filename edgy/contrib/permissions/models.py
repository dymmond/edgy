from typing import ClassVar

import edgy

from .managers import PermissionManager


class BasePermission(edgy.Model):
    """
    Abstract base model for defining permissions within the Edgy framework.

    This model provides a foundational structure for permissions, including
    a name, an optional description, and a custom manager for querying
    permissions. It is designed to be inherited by concrete permission models.
    """

    users_field_group: ClassVar[str] = "users"
    """
    A class variable specifying the name of the field on the group model
    that links back to users. Defaults to "users".
    """

    name: str = edgy.fields.CharField(max_length=100, null=False)
    """
    The unique name of the permission.

    This is a required string field with a maximum length of 100 characters,
    serving as a primary identifier for the permission.
    """
    description: str | None = edgy.fields.ComputedField(  # type: ignore
        getter="get_description",
        setter="set_description",
        fallback_getter=lambda field, instance, owner: instance.name,
    )
    """
    An optional, computed description for the permission.

    This field's value is determined by `get_description` and `set_description`
    methods (which would be defined in a concrete implementation of this model).
    If no description is explicitly set or computed, it falls back to the
    permission's `name`.
    """

    query = PermissionManager()
    """
    Custom manager for the `BasePermission` model.

    This manager provides enhanced querying capabilities specific to permissions,
    such as retrieving permissions based on users or groups.
    """

    class Meta:
        """
        Metadata options for the `BasePermission` model.
        """

        abstract = True
        """
        Specifies that this model is an abstract base class.

        When `True`, Edgy will not create a database table for this model,
        and it is intended to be inherited by other models.
        """
