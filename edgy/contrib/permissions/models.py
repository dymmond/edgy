from typing import ClassVar, Optional

import edgy

from .managers import PermissionManager


class BasePermission(edgy.Model):
    groups_field_user: ClassVar[str] = "groups"
    users_field_group: ClassVar[str] = "users"
    name: str = edgy.fields.CharField(max_length=100, null=False)
    # model_name: str = edgy.fields.CharField(max_length=100, null=True)
    # obj = edgy.fields.ForeignKey("ContentType")
    description: Optional[str] = edgy.fields.ComputedField(  # type: ignore
        getter="get_description",
        setter="set_description",
        # default to name
        fallback_getter=lambda instance, field_name: instance.name,
    )

    # users = edgy.fields.ManyToMany(User)
    # groups = edgy.fields.ManyToMany(Group)

    query = PermissionManager()

    class Meta:
        abstract = True
        # unique_together=[(name, model_name, obj)]
