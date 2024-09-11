from functools import cached_property
from typing import TYPE_CHECKING, Any, Dict, Union

from edgy.core.db.fields.foreign_keys import BaseForeignKeyField, ForeignKey
from edgy.core.terminal import Print

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType

terminal = Print()


class BaseContentTypeFieldField(BaseForeignKeyField):
    async def pre_save_callback(
        self, value: Any, original_value: Any, force_insert: bool, instance: "BaseModelType"
    ) -> Any:
        target = self.target
        if value is None or (isinstance(value, dict) and not value):
            value = original_value
        # e.g. default was a Model
        if isinstance(value, (target, target.proxy_model)):
            value.name = self.owner.__name__
        return await super().pre_save_callback(
            value, original_value, force_insert=force_insert, instance=instance
        )

    def get_default_value(self) -> Any:
        default = getattr(self, "default", None)
        if callable(default):
            # WARNING: here defaults are called with the owner
            return default(self.owner)
        return default

    @cached_property
    def reverse_name(self) -> str:
        return f"reverse_{self.owner.__name__.lower()}"

    @cached_property
    def related_name(self) -> str:
        return f"reverse_{self.owner.__name__.lower()}"


class ContentTypeField(ForeignKey):
    field_bases = (BaseContentTypeFieldField,)

    def __new__(  # type: ignore
        cls,
        to: Union["BaseModelType", str] = "ContentType",
        default: Any = lambda owner: owner.meta.registry.get_model("ContentType")(
            name=owner.__name__
        ),
        **kwargs: Any,
    ) -> "BaseFieldType":
        return super().__new__(cls, to=to, default=default, **kwargs)

    @classmethod
    def validate(cls, kwargs: Dict[str, Any]) -> None:
        for argument in ["related_name", "reverse_name", "unique", "null"]:
            if kwargs.get(argument):
                terminal.write_warning(
                    f"Declaring `{argument}` on a ContentTypeField has no effect."
                )
        kwargs.pop("related_name", None)
        kwargs.pop("reverse_name", None)
        kwargs["unique"] = True
        kwargs["null"] = False
        super().validate(kwargs)
