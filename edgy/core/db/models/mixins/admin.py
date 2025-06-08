from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import ConfigDict

from edgy.core.marshalls import ConfigMarshall, Marshall

if TYPE_CHECKING:
    from edgy.core.db.models import Model


class AdminMixin:
    """
    Admin related mixin.
    """

    @classmethod
    def get_admin_marshall_class(cls: type[Model], *, phase: str) -> type[Marshall]:
        """
        Generate a marshall class for the admin.

        Can be dynamic for the current user.
        """

        class AdminMarshall(Marshall):
            model_config: ClassVar[ConfigDict] = ConfigDict(title=cls.__name__)
            marshall_config = ConfigMarshall(model=cls, fields=["__all__"])

        if phase == "schema":
            # this triggers additionalProperties=false
            AdminMarshall.model_config["extra"] = "forbid"
        return AdminMarshall

    @classmethod
    def get_admin_marshall_for_save(
        cls: type[Model], instance: Model | None = None, /, **kwargs: Any
    ) -> Marshall:
        """Generate a marshall instance from an instance for the admin.

        Can be dynamic for the current user. Called in the create/edit path.
        """
        return cls.get_admin_marshall_class(phase="update" if instance is not None else "create")(
            instance, **kwargs
        )
