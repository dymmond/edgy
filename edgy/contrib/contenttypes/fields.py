from functools import cached_property
from typing import Any, Dict

from edgy.core.db.fields.foreign_keys import BaseForeignKeyField, ForeignKey
from edgy.core.terminal import Print

terminal = Print()


class BaseGenericForeignKeyField(BaseForeignKeyField):
    pass


class GenericForeignKey(ForeignKey):
    field_bases = (BaseGenericForeignKeyField,)

    @classmethod
    def validate(cls, kwargs: Dict[str, Any]) -> None:
        super().validate(kwargs)
        for argument in ["related_name", "reverse_name", "unique", "null"]:
            if kwargs.get(argument):
                terminal.write_warning(
                    f"Declaring `{argument}` on a GenericForeignKey has no effect."
                )
        kwargs.pop("related_name", None)
        kwargs.pop("reverse_name", None)
        kwargs["unique"] = True
        kwargs["null"] = False
        kwargs.setdefault(
            "default", lambda owner: owner.registry["ContentType"](model_name=owner.__name__)
        )

    @cached_property
    def reverse_name(self) -> str:
        return f"reverse_{self.owner.__name__.lower()}"

    @cached_property
    def related_name(self) -> str:
        return f"reverse_{self.owner.__name__.lower()}"

    def has_default(self) -> bool:
        return True

    def get_default_value(self) -> Any:
        default = getattr(self, "default", None)
        if callable(default):
            # WARNING: here defaults are called with the owner
            return default(self.owner)
        return default
