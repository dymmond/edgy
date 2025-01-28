from typing import TYPE_CHECKING, ClassVar, cast

import edgy

from .metaclasses import ContentTypeMeta

if TYPE_CHECKING:
    from edgy.core.db.querysets.base import QuerySet


class ContentType(edgy.Model, metaclass=ContentTypeMeta):
    no_constraint: ClassVar[bool] = False

    class Meta:
        abstract = True

    # NOTE: model_ is a private namespace of pydantic
    # model names shouldn't be so long, maybe a check would be appropriate
    name: str = edgy.fields.CharField(max_length=100, default="", index=True)
    # set also the schema for tenancy support
    schema_name: str = edgy.CharField(max_length=63, null=True, index=True)
    # can be a hash or similar. Usefull for checking collisions cross domain
    collision_key: str = edgy.fields.CharField(max_length=255, null=True, unique=True)

    async def get_instance(self) -> edgy.Model:
        reverse_name = f"reverse_{self.name.lower()}"
        return (
            await cast("QuerySet", getattr(self, reverse_name))
            .using(schema=self.schema_name)
            .get()
        )

    async def delete(
        self, skip_post_delete_hooks: bool = False, remove_referenced_call: bool = False
    ) -> None:
        await super().delete(skip_post_delete_hooks=skip_post_delete_hooks)
        if remove_referenced_call:
            return
        reverse_name = f"reverse_{self.name.lower()}"
        referenced_obs = cast("QuerySet", getattr(self, reverse_name))
        if self.meta.fields[reverse_name].foreign_key.force_cascade_deletion_relation:
            await referenced_obs.using(schema=self.schema_name).delete()
