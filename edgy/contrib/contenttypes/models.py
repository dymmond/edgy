from typing import TYPE_CHECKING, ClassVar, cast

import edgy

from .metaclasses import ContentTypeMeta

if TYPE_CHECKING:
    from edgy.core.db.fields.foreign_keys import BaseForeignKeyField
    from edgy.core.db.querysets.base import QuerySet


class ContentType(edgy.Model, metaclass=ContentTypeMeta):
    no_constraint: ClassVar[bool] = False

    class Meta:
        abstract = True
        no_admin_create = True

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

    async def raw_delete(
        self, *, skip_post_delete_hooks: bool, remove_referenced_call: bool | str
    ) -> None:
        await super().raw_delete(
            skip_post_delete_hooks=skip_post_delete_hooks,
            remove_referenced_call=remove_referenced_call,
        )
        if remove_referenced_call:
            return
        reverse_name = f"reverse_{self.name.lower()}"
        if not hasattr(self, reverse_name):
            # e.g. model was removed from registry
            return
        referenced_obs = cast("QuerySet", getattr(self, reverse_name))
        fk = cast("BaseForeignKeyField", self.meta.fields[reverse_name].foreign_key)
        if fk.force_cascade_deletion_relation:
            await referenced_obs.using(schema=self.schema_name).raw_delete(
                use_models=fk.use_model_based_deletion, remove_referenced_call=reverse_name
            )
