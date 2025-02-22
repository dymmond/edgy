from typing import ClassVar, Optional

import edgy

from .managers import PermissionManager


class BasePermission(edgy.Model):
    users_field_group: ClassVar[str] = "users"
    name: str = edgy.fields.CharField(max_length=100, null=False)
    description: Optional[str] = edgy.fields.ComputedField(
        getter="get_description",
        setter="set_description",
        fallback_getter=lambda field, instance, owner: instance.name,
    )

    query = PermissionManager()

    class Meta:
        abstract = True
