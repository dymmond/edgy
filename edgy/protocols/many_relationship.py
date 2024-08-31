from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: nocover
    from edgy.core.db.models.types import BaseModelType


@runtime_checkable
class ManyRelationProtocol(Protocol):
    instance: Any

    """Defines the what needs to be implemented when using the ManyRelationProtocol"""

    async def save_related(self) -> None: ...

    async def add(self, child: "BaseModelType") -> Optional["BaseModelType"]: ...

    def stage(self, *children: "BaseModelType") -> None:
        """Lazy add children"""

    async def remove(self, child: Optional["BaseModelType"] = None) -> None: ...
