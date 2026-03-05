from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from sqlalchemy.ext.asyncio import AsyncTransaction

if False:  # pragma: no cover
    from .connection import Database


class Transaction:
    """Async transaction context manager with decorator support."""

    def __init__(
        self,
        database: Database,
        *,
        force_rollback: bool = False,
        **kwargs: Any,
    ) -> None:
        self._database = database
        self._force_rollback = force_rollback
        self._kwargs = kwargs
        self._transaction: AsyncTransaction | None = None
        self._joined_existing: bool = False
        self._entered_database: bool = False

    async def __aenter__(self) -> Transaction:
        if self._database._current_connection() is None:
            self._entered_database = True
            await self._database.__aenter__()

        connection = self._database._require_connection()
        if connection.in_transaction():
            if self._database._in_user_transaction():
                if self._force_rollback:
                    self._transaction = await connection.begin_nested()
                else:
                    self._joined_existing = True
            elif self._database._effective_force_rollback():
                # Join the force-rollback root transaction by default so writes stay rollbackable.
                if self._force_rollback:
                    self._transaction = await connection.begin_nested()
                else:
                    self._joined_existing = True
            else:
                # Clear any implicit transaction so we can start an explicit one.
                await connection.rollback()
                self._transaction = await connection.begin()
        else:
            self._transaction = await connection.begin()
        self._database._push_transaction_depth()
        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        self._database._pop_transaction_depth()
        transaction = self._transaction
        self._transaction = None
        self._joined_existing = False

        if transaction is not None and transaction.is_active:
            if exc_type is not None or self._force_rollback:
                await transaction.rollback()
            else:
                await transaction.commit()

        if self._entered_database:
            self._entered_database = False
            await self._database.__aexit__(exc_type, exc_value, traceback)
        return False

    def __call__(self, fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        """Use transactions as async function decorators."""

        @wraps(fn)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            async with self._database.transaction(
                force_rollback=self._force_rollback,
                **self._kwargs,
            ):
                return await fn(*args, **kwargs)

        return wrapped


__all__ = ["Transaction"]
