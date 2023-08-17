from typing import TYPE_CHECKING, runtime_checkable

try:
    from typing import Protocol
except ImportError:  # pragma: nocover
    from typing_extensions import Protocol  # type: ignore


if TYPE_CHECKING:  # pragma: nocover
    from edgy import Model


@runtime_checkable
class ManyRelationProtocol(Protocol):
    """Defines the what needs to be implemented when using the ManyRelationProtocol"""

    async def add(self, child: "Model") -> None:
        ...

    async def remove(self, child: "Model") -> None:
        ...
