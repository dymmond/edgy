from typing import ClassVar, Optional

import edgy

from .managers import PermissionManager


class BasePermission(edgy.Model):
    users_field_group: ClassVar[str] = "users"
    name: str = edgy.fields.CharField(max_length=100, null=False)
    # model_name: str = edgy.fields.CharField(max_length=100, null=True)
    # obj = edgy.fields.ForeignKey("ContentType")
    description: Optional[str] = edgy.fields.ComputedField(  # type: ignore
        getter="get_description",
        setter="set_description",
        # default to name
        fallback_getter=lambda field, instance, owner: instance.name,
    )

    # Important: embed_through must be set for enabling full proxying
    # users = edgy.fields.ManyToMany("User", embed_through=False)
    # groups = edgy.fields.ManyToMany("Group", embed_through=False)

    query = PermissionManager()

    class Meta:
        abstract = True
        # unique_together=[(name, model_name, obj)]
