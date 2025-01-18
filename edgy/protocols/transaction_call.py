from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from databasez.core.transaction import Transaction


class TransactionCallProtocol(Protocol):
    def __call__(instance: Any, *, force_rollback: bool = False, **kwargs: Any) -> Transaction: ...
