from typing import TYPE_CHECKING, Any, Optional, Union, cast

import edgy
from edgy.core.db.context_vars import CURRENT_PHASE
from edgy.core.db.fields.base import BaseField
from edgy.core.db.fields.factories import ForeignKeyFieldFactory
from edgy.exceptions import ModelReferenceError
from edgy.utils.compat import is_class_and_subclass

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.model_reference import ModelRef
    from edgy.core.db.models.types import BaseModelType


class BaseRefForeignKey(BaseField): ...


class RefForeignKey(ForeignKeyFieldFactory, list):
    field_type = list
    field_bases = (BaseRefForeignKey,)

    @classmethod
    def modify_input(
        cls,
        field_obj: "BaseFieldType",
        name: str,
        kwargs: dict[str, Any],
        original_fn: Any = None,
    ) -> None:
        phase = CURRENT_PHASE.get()
        # we are empty
        if name not in kwargs and phase == "init_db":
            kwargs[name] = []

    def embed_field(
        self,
        prefix: str,
        new_fieldname: str,
        owner: Optional[type["BaseModelType"]] = None,
        parent: Optional["BaseFieldType"] = None,
    ) -> Optional["BaseFieldType"]:
        return None

    def __new__(cls, to: "ModelRef", null: bool = False) -> "BaseFieldType":  # type: ignore
        if not is_class_and_subclass(to, edgy.ModelRef):
            raise ModelReferenceError(
                detail="A model reference must be an object of type ModelRef"
            )
        if not getattr(to, "__related_name__", None):
            raise ModelReferenceError(
                "'__related_name__' must be declared when subclassing ModelRef."
            )

        return super().__new__(cls, to=to, exclude=True, null=null)

    @classmethod
    async def post_save_callback(
        cls,
        field_obj: "BaseFieldType",
        value: Optional[list],
        instance: "BaseModelType",
        force_insert: bool,
        original_fn: Any = None,
    ) -> None:
        if not value:
            return
        model_ref = field_obj.to

        relation_field = instance.meta.fields[model_ref.__related_name__]
        extra_params = {}
        try:
            # m2m or foreign key
            target_model_class = relation_field.target
        except AttributeError:
            # reverse m2m or foreign key
            target_model_class = relation_field.related_from
        if not relation_field.is_m2m:
            # sometimes the foreign key is required, so set it already
            extra_params[relation_field.foreign_key.name] = instance
        relation = getattr(instance, model_ref.__related_name__)
        while value:
            instance_or_dict: Union[dict, ModelRef] = value.pop()
            if isinstance(instance_or_dict, dict):
                instance_or_dict = model_ref(**instance_or_dict)
            model = target_model_class(
                **cast("ModelRef", instance_or_dict).model_dump(exclude={"__related_name__"}),
                **extra_params,
            )
            # we are in a relationship field
            await relation.add(model)
