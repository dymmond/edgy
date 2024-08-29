from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: nocover
    from edgy import Model


@runtime_checkable
class ManyRelationProtocol(Protocol):
    instance: Any

    """Defines the what needs to be implemented when using the ManyRelationProtocol"""

    async def save_related(self) -> None: ...

    async def add(self, child: "Model") -> Optional["Model"]: ...

    def stage(self, *children: "Model") -> None:
        """Lazy add children"""

    async def remove(self, child: Optional["Model"] = None) -> None: ...
