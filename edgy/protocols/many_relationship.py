from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: nocover
    from edgy import Model


@runtime_checkable
class ManyRelationProtocol(Protocol):
    """Defines the what needs to be implemented when using the ManyRelationProtocol"""
    async def save_related(self) -> None: ...

    async def add(self, child: "Model") -> None: ...

    async def remove(self, child: "Model") -> None: ...
