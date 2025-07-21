from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from databasez.core.transaction import Transaction


class TransactionCallProtocol(Protocol):
    """
    Defines the callable interface for initiating a database transaction.

    This protocol specifies that an object implementing it must be callable.
    When called, it is expected to return a `Transaction` instance, enabling
    transactional database operations. This is particularly useful for type
    hinting and ensuring consistency across different transaction managers.
    """

    def __call__(
        self, instance: Any, *, force_rollback: bool = False, **kwargs: Any
    ) -> Transaction:
        """
        Initiates and returns a database transaction.

        This method defines the signature for any callable that provides
        transactional capabilities. It allows for an instance context,
        a flag to force rollback, and additional keyword arguments for
        transaction configuration.

        Parameters:
            instance (Any): An instance related to the transaction, typically
                            a database client or a model instance. This parameter
                            provides context for the transaction.
            force_rollback (bool): If `True`, the transaction will be explicitly
                                   rolled back regardless of success or failure
                                   during its execution. This is primarily used
                                   for testing purposes. Defaults to `False`.
            **kwargs (Any): Additional keyword arguments that can be passed to
                            configure the transaction (e.g., isolation level).

        Returns:
            Transaction: An instance of `databasez.core.transaction.Transaction`
                         representing the started database transaction.
        """
        ...
