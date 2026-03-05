from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from .connection import Database
from .url import DatabaseURL


class DatabaseTestClient(Database):
    """Database helper specialized for test database lifecycle management."""

    testclient_default_test_prefix: str = "test_"
    testclient_default_lazy_setup: bool = True
    testclient_default_force_rollback: bool = False
    testclient_default_use_existing: bool = False
    testclient_default_drop_database: bool = False
    testclient_default_full_isolation: bool = True

    def __init__(
        self,
        url: str | DatabaseURL | Database,
        *,
        force_rollback: bool | None = None,
        lazy_setup: bool | None = None,
        use_existing: bool | None = None,
        drop_database: bool | None = None,
        full_isolation: bool | None = None,
        test_prefix: str | None = None,
        **kwargs: Any,
    ) -> None:
        test_prefix = self.testclient_default_test_prefix if test_prefix is None else test_prefix
        lazy_setup = self.testclient_default_lazy_setup if lazy_setup is None else lazy_setup
        use_existing = (
            self.testclient_default_use_existing if use_existing is None else use_existing
        )
        drop_database = (
            self.testclient_default_drop_database if drop_database is None else drop_database
        )
        force_rollback = (
            self.testclient_default_force_rollback if force_rollback is None else force_rollback
        )
        full_isolation = (
            self.testclient_default_full_isolation if full_isolation is None else full_isolation
        )

        parsed_url = self._build_test_database_url(url, test_prefix=test_prefix)

        super().__init__(
            parsed_url,
            force_rollback=force_rollback,
            full_isolation=full_isolation,
            **kwargs,
        )

        self.test_prefix = test_prefix
        self.lazy_setup = lazy_setup
        self.use_existing = use_existing
        self.drop = drop_database

        self._setup_done: bool = False
        self._lifespan_depth: int = 0
        self._lifespan_owner_stack: list[bool] = []

    async def __aenter__(self) -> DatabaseTestClient:
        owns_database_lifecycle = self._lifespan_depth == 0 and self._persistent_connection is None
        if self._lifespan_depth == 0:
            await self._setup_if_needed()
        self._lifespan_depth += 1
        self._lifespan_owner_stack.append(owns_database_lifecycle)
        try:
            await super().__aenter__()
        except BaseException:
            self._lifespan_depth = max(0, self._lifespan_depth - 1)
            if self._lifespan_owner_stack:
                self._lifespan_owner_stack.pop()
            raise
        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        await super().__aexit__(exc_type, exc_value, traceback)
        owns_database_lifecycle = (
            self._lifespan_owner_stack.pop() if self._lifespan_owner_stack else False
        )
        self._lifespan_depth = max(0, self._lifespan_depth - 1)
        if self._lifespan_depth == 0 and owns_database_lifecycle and self.drop:
            await self.drop_database(self.url)

    async def connect(self) -> None:
        await self._setup_if_needed()
        await super().connect()

    async def disconnect(self) -> None:
        was_connected = self.is_connected
        await super().disconnect()
        if was_connected and self.drop and self._lifespan_depth == 0:
            await self.dispose()
            self._engine = None
            await self._drop_database(self.url)
            self._setup_done = False

    async def is_database_exist(self) -> bool:
        return await self._is_database_exist(self.url)

    async def create_database(self, url: str | DatabaseURL | None = None) -> None:
        db_url = (
            self.url
            if url is None
            else (url if isinstance(url, DatabaseURL) else DatabaseURL(url))
        )
        await self._create_database(db_url)

    async def drop_database(self, url: str | DatabaseURL | None = None) -> None:
        db_url = (
            self.url
            if url is None
            else (url if isinstance(url, DatabaseURL) else DatabaseURL(url))
        )
        await super().disconnect()
        await self.dispose()
        self._engine = None
        await self._drop_database(db_url)
        self._setup_done = False

    async def _setup_if_needed(self) -> None:
        if self._setup_done and self.lazy_setup:
            return

        exists = await self._is_database_exist(self.url)
        if exists and not self.use_existing:
            await self._drop_database(self.url)
            exists = False

        if not exists:
            await self._create_database(self.url)

        self._setup_done = True

    @staticmethod
    def _build_test_database_url(
        url: str | DatabaseURL | Database,
        *,
        test_prefix: str,
    ) -> DatabaseURL:
        if isinstance(url, Database):
            base_url = url.url
        elif isinstance(url, DatabaseURL):
            base_url = url
        else:
            base_url = DatabaseURL(url)

        database_name = base_url.database
        if not test_prefix or database_name in (None, "", ":memory:"):
            return base_url
        if database_name.startswith(test_prefix):
            return base_url
        return base_url.replace(database=f"{test_prefix}{database_name}")

    async def _is_database_exist(self, db_url: DatabaseURL) -> bool:
        dialect = db_url.dialect
        if dialect.startswith("postgres"):
            return await self._is_postgres_database_exist(db_url)
        if dialect == "mysql":
            return await self._is_mysql_database_exist(db_url)
        if dialect == "sqlite":
            database_name = db_url.database
            if database_name in (None, "", ":memory:"):
                return True
            return Path(database_name).exists()
        raise NotImplementedError(
            f"Database existence checks are not implemented for {dialect!r}."
        )

    async def _create_database(self, db_url: DatabaseURL) -> None:
        dialect = db_url.dialect
        if dialect.startswith("postgres"):
            await self._create_postgres_database(db_url)
            return
        if dialect == "mysql":
            await self._create_mysql_database(db_url)
            return
        if dialect == "sqlite":
            database_name = db_url.database
            if database_name in (None, "", ":memory:"):
                return
            path = Path(database_name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
            return
        raise NotImplementedError(f"Database creation is not implemented for {dialect!r}.")

    async def _drop_database(self, db_url: DatabaseURL) -> None:
        dialect = db_url.dialect
        if dialect.startswith("postgres"):
            await self._drop_postgres_database(db_url)
            return
        if dialect == "mysql":
            await self._drop_mysql_database(db_url)
            return
        if dialect == "sqlite":
            database_name = db_url.database
            if database_name in (None, "", ":memory:"):
                return
            Path(database_name).unlink(missing_ok=True)
            return
        raise NotImplementedError(f"Database deletion is not implemented for {dialect!r}.")

    async def _is_postgres_database_exist(self, db_url: DatabaseURL) -> bool:
        admin_url = db_url.replace(database="postgres")
        engine = create_async_engine(
            self._build_engine_url(admin_url), isolation_level="AUTOCOMMIT"
        )
        try:
            async with engine.connect() as connection:
                result = await connection.execute(
                    sqlalchemy.text("SELECT 1 FROM pg_database WHERE datname = :name"),
                    {"name": db_url.database},
                )
                return result.scalar_one_or_none() is not None
        finally:
            await engine.dispose()

    async def _create_postgres_database(self, db_url: DatabaseURL) -> None:
        if await self._is_postgres_database_exist(db_url):
            return
        admin_url = db_url.replace(database="postgres")
        engine = create_async_engine(
            self._build_engine_url(admin_url), isolation_level="AUTOCOMMIT"
        )
        try:
            async with engine.connect() as connection:
                quoted = connection.dialect.identifier_preparer.quote(db_url.database or "")
                await connection.execute(sqlalchemy.text(f"CREATE DATABASE {quoted}"))
        finally:
            await engine.dispose()

    async def _drop_postgres_database(self, db_url: DatabaseURL) -> None:
        admin_url = db_url.replace(database="postgres")
        engine = create_async_engine(
            self._build_engine_url(admin_url), isolation_level="AUTOCOMMIT"
        )
        try:
            async with engine.connect() as connection:
                await connection.execute(
                    sqlalchemy.text(
                        "SELECT pg_terminate_backend(pid) "
                        "FROM pg_stat_activity "
                        "WHERE datname = :name AND pid <> pg_backend_pid()"
                    ),
                    {"name": db_url.database},
                )
                quoted = connection.dialect.identifier_preparer.quote(db_url.database or "")
                await connection.execute(sqlalchemy.text(f"DROP DATABASE IF EXISTS {quoted}"))
        finally:
            await engine.dispose()

    async def _is_mysql_database_exist(self, db_url: DatabaseURL) -> bool:
        admin_url = db_url.replace(database=None)
        engine = create_async_engine(
            self._build_engine_url(admin_url), isolation_level="AUTOCOMMIT"
        )
        try:
            async with engine.connect() as connection:
                result = await connection.execute(
                    sqlalchemy.text(
                        "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = :name"
                    ),
                    {"name": db_url.database},
                )
                return result.scalar_one_or_none() is not None
        finally:
            await engine.dispose()

    async def _create_mysql_database(self, db_url: DatabaseURL) -> None:
        if await self._is_mysql_database_exist(db_url):
            return
        admin_url = db_url.replace(database=None)
        engine = create_async_engine(
            self._build_engine_url(admin_url), isolation_level="AUTOCOMMIT"
        )
        try:
            async with engine.connect() as connection:
                quoted = connection.dialect.identifier_preparer.quote(db_url.database or "")
                await connection.execute(sqlalchemy.text(f"CREATE DATABASE {quoted}"))
        finally:
            await engine.dispose()

    async def _drop_mysql_database(self, db_url: DatabaseURL) -> None:
        admin_url = db_url.replace(database=None)
        engine = create_async_engine(
            self._build_engine_url(admin_url), isolation_level="AUTOCOMMIT"
        )
        try:
            async with engine.connect() as connection:
                quoted = connection.dialect.identifier_preparer.quote(db_url.database or "")
                await connection.execute(sqlalchemy.text(f"DROP DATABASE IF EXISTS {quoted}"))
        finally:
            await engine.dispose()


# Keep env overrides compatible with previous behavior.
if "EDGY_TESTCLIENT_TEST_PREFIX" in os.environ:
    DatabaseTestClient.testclient_default_test_prefix = os.environ["EDGY_TESTCLIENT_TEST_PREFIX"]
DatabaseTestClient.testclient_default_lazy_setup = (
    os.environ.get("EDGY_TESTCLIENT_LAZY_SETUP", "true") or ""
).lower() == "true"
DatabaseTestClient.testclient_default_force_rollback = (
    os.environ.get("EDGY_TESTCLIENT_FORCE_ROLLBACK") or ""
).lower() == "true"
DatabaseTestClient.testclient_default_use_existing = (
    os.environ.get("EDGY_TESTCLIENT_USE_EXISTING") or ""
).lower() == "true"
DatabaseTestClient.testclient_default_drop_database = (
    os.environ.get("EDGY_TESTCLIENT_DROP_DATABASE") or ""
).lower() == "true"
DatabaseTestClient.testclient_default_full_isolation = (
    os.environ.get("EDGY_TESTCLIENT_FULL_ISOLATION", "true") or ""
).lower() == "true"


__all__ = ["DatabaseTestClient"]
