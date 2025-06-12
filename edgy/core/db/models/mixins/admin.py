from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import ConfigDict

from edgy.core.marshalls.base import Marshall
from edgy.core.marshalls.config import ConfigMarshall

if TYPE_CHECKING:
    from edgy.core.db.models import Model


class AdminMixin:
    """
    Admin related mixin.
    """

    @classmethod
    def get_admin_marshall_config(
        cls: type[Model], *, phase: str, for_schema: bool
    ) -> dict[str, Any]:
        """
        Shortcut for updating the marshall_config of the admin marshall.

        Can be dynamic for the current user.
        """
        return {"fields": ["__all__"]}

    @classmethod
    def get_admin_marshall_class(
        cls: type[Model], *, phase: str, for_schema: bool = False
    ) -> type[Marshall]:
        """
        Generate a marshall class for the admin.

        Can be dynamic for the current user.
        """

        class AdminMarshall(Marshall):
            # forbid triggers additionalProperties=false
            model_config: ClassVar[ConfigDict] = ConfigDict(
                title=cls.__name__, extra="forbid" if for_schema else None
            )
            marshall_config = ConfigMarshall(
                model=cls,
                **cls.get_admin_marshall_config(phase=phase, for_schema=for_schema),  # type: ignore
            )

        return AdminMarshall

    @classmethod
    def get_admin_marshall_for_save(
        cls: type[Model], instance: Model | None = None, /, **kwargs: Any
    ) -> Marshall:
        """Generate a marshall instance from an instance for the admin.

        Can be dynamic for the current user. Called in the create/edit path.
        """
        return cls.get_admin_marshall_class(
            phase="update" if instance is not None else "create", for_schema=False
        )(instance, **kwargs)
