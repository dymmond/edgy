from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

import sqlalchemy
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncTransaction,
    create_async_engine,
)
from sqlalchemy.sql.dml import Insert

from .transaction import Transaction
from .url import DatabaseURL

_ASYNC_DRIVER_BY_DIALECT: dict[str, str] = {
    "postgresql": "asyncpg",
    "postgres": "asyncpg",
    "sqlite": "aiosqlite",
    "mysql": "aiomysql",
    "mssql": "aioodbc",
}


@dataclass(frozen=True)
class _ConnectionState:
    connection: AsyncConnection
    owns_connection: bool
    force_rollback_transaction: AsyncTransaction | None = None


class _ForceRollbackContext:
    def __init__(self, database: Database, force_rollback: bool) -> None:
        self._database = database
        self._force_rollback = force_rollback
        self._token: Token[tuple[bool, ...]] | None = None

    def __enter__(self) -> _ForceRollbackContext:
        overrides = self._database._force_rollback_overrides.get()
        self._token = self._database._force_rollback_overrides.set(
            (*overrides, self._force_rollback)
        )
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        token = self._token
        self._token = None
        if token is not None:
            self._database._force_rollback_overrides.reset(token)
        return False


class _ForceRollbackProxy:
    """Boolean + callable adapter used for API compatibility."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def __bool__(self) -> bool:
        return self._database._effective_force_rollback()

    def __call__(self, force_rollback: bool = True) -> _ForceRollbackContext:
        return self._database._force_rollback_context(force_rollback)

    def __repr__(self) -> str:
        return repr(bool(self))


class Database:
    """SQLAlchemy-backed async database helper compatible with Edgy's expectations."""

    def __init__(
        self,
        url: str | DatabaseURL | Database,
        *,
        force_rollback: bool = False,
        full_isolation: bool = False,
        **engine_options: Any,
    ) -> None:
        source: Database | None = url if isinstance(url, Database) else None
        source_url = source.url if source is not None else url

        self.url = source_url if isinstance(source_url, DatabaseURL) else DatabaseURL(source_url)
        self.dsn = str(self.url)

        inherited_engine_options = getattr(source, "_engine_options", {}) if source else {}
        self._engine_options: dict[str, Any] = {**inherited_engine_options, **engine_options}

        self._force_rollback_default = force_rollback
        self._force_rollback_overrides: ContextVar[tuple[bool, ...]] = ContextVar(
            "edgy_force_rollback_overrides", default=()
        )
        self.force_rollback = _ForceRollbackProxy(self)

        self.full_isolation = full_isolation

        self._engine: AsyncEngine | None = None
        self._engine_url: str = self._build_engine_url(self.url)

        self._persistent_connection: AsyncConnection | None = None
        self._persistent_force_rollback_transaction: AsyncTransaction | None = None

        self._connection_stack: ContextVar[tuple[_ConnectionState, ...]] = ContextVar(
            "edgy_connection_stack", default=()
        )
        self._transaction_depth: ContextVar[int] = ContextVar("edgy_transaction_depth", default=0)

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_async_engine(self._engine_url, **self._engine_options)
        return self._engine

    @property
    def sync_engine(self) -> sqlalchemy.Engine:
        return self.engine.sync_engine

    @property
    def is_connected(self) -> bool:
        return self._persistent_connection is not None

    async def connect(self) -> None:
        if self._persistent_connection is not None:
            return

        connection = await self.engine.connect()
        force_tx: AsyncTransaction | None = None
        if self._effective_force_rollback():
            force_tx = await connection.begin()

        self._persistent_connection = connection
        self._persistent_force_rollback_transaction = force_tx

    async def disconnect(self) -> None:
        connection = self._persistent_connection
        if connection is None:
            return

        force_tx = self._persistent_force_rollback_transaction
        self._persistent_force_rollback_transaction = None
        if force_tx is not None and force_tx.is_active:
            await force_tx.rollback()

        self._persistent_connection = None
        await connection.close()

    async def dispose(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()

    async def __aenter__(self) -> Database:
        stack = self._connection_stack.get()
        if stack:
            self._connection_stack.set(
                (*stack, _ConnectionState(connection=stack[-1].connection, owns_connection=False))
            )
            return self

        if self._persistent_connection is not None:
            self._connection_stack.set(
                (
                    _ConnectionState(
                        connection=self._persistent_connection,
                        owns_connection=False,
                    ),
                )
            )
            return self

        connection = await self.engine.connect()
        force_tx: AsyncTransaction | None = None
        if self._effective_force_rollback():
            force_tx = await connection.begin()
        self._connection_stack.set(
            (
                _ConnectionState(
                    connection=connection,
                    owns_connection=True,
                    force_rollback_transaction=force_tx,
                ),
            )
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        stack = self._connection_stack.get()
        if not stack:
            return

        state = stack[-1]
        self._connection_stack.set(stack[:-1])

        if not state.owns_connection:
            return

        if (
            state.force_rollback_transaction is not None
            and state.force_rollback_transaction.is_active
        ):
            await state.force_rollback_transaction.rollback()
        await state.connection.close()

    def transaction(self, *, force_rollback: bool = False, **kwargs: Any) -> Transaction:
        return Transaction(self, force_rollback=force_rollback, **kwargs)

    async def run_sync(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        async with self:
            connection = self._require_connection()
            try:
                result = await connection.run_sync(fn, *args, **kwargs)
            except BaseException:
                await self._finalize_connection_transaction(connection, success=False)
                raise
            await self._finalize_connection_transaction(connection, success=True)
            return result

    async def fetch_all(self, expression: Any) -> list[sqlalchemy.Row]:
        async with self:
            connection = self._require_connection()
            try:
                result = await connection.execute(expression)
                rows = list(result.fetchall())
            except BaseException:
                await self._finalize_connection_transaction(connection, success=False)
                raise
            await self._finalize_connection_transaction(connection, success=True)
            return rows

    async def fetch_one(self, expression: Any, pos: int = 0) -> sqlalchemy.Row | None:
        rows = await self.fetch_all(expression)
        if pos < 0:
            return None
        if len(rows) <= pos:
            return None
        return rows[pos]

    async def fetch_val(self, expression: Any) -> Any:
        row = await self.fetch_one(expression)
        if row is None:
            return None
        if hasattr(row, "_mapping"):
            mapping = row._mapping
            if mapping:
                return next(iter(mapping.values()))
        values = tuple(row)
        return values[0] if values else None

    async def execute(self, expression: Any) -> Any:
        async with self:
            connection = self._require_connection()
            try:
                result = await connection.execute(expression)
                value = self._normalize_execute_result(expression, result)
            except BaseException:
                await self._finalize_connection_transaction(connection, success=False)
                raise
            await self._finalize_connection_transaction(connection, success=True)
            return value

    async def execute_many(
        self,
        expression: Any,
        values: Sequence[Mapping[str, Any]] | None = None,
    ) -> Any:
        async with self:
            connection = self._require_connection()
            try:
                if values is None:
                    result = await connection.execute(expression)
                else:
                    result = await connection.execute(expression, list(values))
            except BaseException:
                await self._finalize_connection_transaction(connection, success=False)
                raise
            await self._finalize_connection_transaction(connection, success=True)
            return result.rowcount

    async def batched_iterate(
        self,
        expression: Any,
        *,
        batch_size: int | None = None,
    ) -> AsyncGenerator[Sequence[sqlalchemy.Row], None]:
        async with self:
            connection = self._require_connection()
            try:
                result = await connection.execute(expression)
                rows = list(result.fetchall())
            except BaseException:
                await self._finalize_connection_transaction(connection, success=False)
                raise
            await self._finalize_connection_transaction(connection, success=True)
            if not rows:
                return
            if batch_size is None or batch_size <= 0:
                yield rows
                return
            for start in range(0, len(rows), batch_size):
                yield rows[start : start + batch_size]

    def _force_rollback_context(self, force_rollback: bool = True) -> _ForceRollbackContext:
        return _ForceRollbackContext(self, force_rollback=force_rollback)

    def _effective_force_rollback(self) -> bool:
        overrides = self._force_rollback_overrides.get()
        if overrides:
            return overrides[-1]
        return self._force_rollback_default

    def _current_connection(self) -> AsyncConnection | None:
        stack = self._connection_stack.get()
        if stack:
            return stack[-1].connection
        return self._persistent_connection

    def _require_connection(self) -> AsyncConnection:
        connection = self._current_connection()
        if connection is None:
            raise RuntimeError("No active database connection.")
        return connection

    def _push_transaction_depth(self) -> None:
        current = self._transaction_depth.get()
        self._transaction_depth.set(current + 1)

    def _pop_transaction_depth(self) -> None:
        current = self._transaction_depth.get()
        self._transaction_depth.set(max(0, current - 1))

    def _in_user_transaction(self) -> bool:
        return self._transaction_depth.get() > 0

    def _should_finalize_connection_transaction(self) -> bool:
        if self._effective_force_rollback():
            return False
        if self._in_user_transaction():
            return False
        return True

    async def _finalize_connection_transaction(
        self, connection: AsyncConnection, *, success: bool
    ) -> None:
        if not self._should_finalize_connection_transaction():
            return
        if not connection.in_transaction():
            return
        if success:
            await connection.commit()
        else:
            await connection.rollback()

    def _normalize_execute_result(self, expression: Any, result: Any) -> Any:
        if isinstance(expression, Insert):
            if result.returns_rows:
                row = result.first()
                if row is not None:
                    return row
            inserted_primary_key = getattr(result, "inserted_primary_key", None)
            if inserted_primary_key:
                if len(inserted_primary_key) == 1:
                    return inserted_primary_key[0]
                return tuple(inserted_primary_key)
        return result.rowcount

    def _build_engine_url(self, url: DatabaseURL) -> str:
        dialect = url.dialect
        driver = url.driver
        if driver is None:
            async_driver = _ASYNC_DRIVER_BY_DIALECT.get(dialect)
            if async_driver is not None:
                return str(url.replace(dialect=dialect, driver=async_driver))
            return str(url)

        if dialect == "sqlite" and driver != "aiosqlite":
            return str(url.replace(dialect=dialect, driver="aiosqlite"))
        return str(url)


__all__ = ["Database", "DatabaseURL"]
