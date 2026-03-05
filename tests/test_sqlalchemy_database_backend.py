import asyncio
from pathlib import Path

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncEngine

from edgy._db.connection import Database

pytestmark = pytest.mark.anyio


def _database_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path}"


def _build_items_table(metadata: sqlalchemy.MetaData) -> sqlalchemy.Table:
    return sqlalchemy.Table(
        "items",
        metadata,
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
        sqlalchemy.Column("name", sqlalchemy.String(length=100), nullable=False),
    )


async def _dispose_database(db: Database) -> None:
    await db.disconnect()
    await db.dispose()


async def test_engine_initialization_exposes_sync_and_async_engines(tmp_path: Path) -> None:
    db = Database(_database_url(tmp_path / "engine.db"))
    try:
        assert isinstance(db.engine, AsyncEngine)
        assert isinstance(db.sync_engine, sqlalchemy.Engine)
        assert db.engine.url.drivername == "sqlite+aiosqlite"
    finally:
        await _dispose_database(db)


async def test_connection_lifecycle_and_context_manager(tmp_path: Path) -> None:
    db = Database(_database_url(tmp_path / "lifecycle.db"))
    try:
        assert not db.is_connected
        async with db:
            assert db._current_connection() is not None  # internal API parity check
        assert db._current_connection() is None

        await db.connect()
        assert db.is_connected
        persistent = db._persistent_connection
        async with db:
            assert db._current_connection() is persistent
        assert db.is_connected
    finally:
        await _dispose_database(db)
    assert not db.is_connected


async def test_execute_commit_and_force_rollback_transaction(tmp_path: Path) -> None:
    db = Database(_database_url(tmp_path / "tx.db"))
    metadata = sqlalchemy.MetaData()
    items = _build_items_table(metadata)

    try:
        await db.run_sync(metadata.create_all)
        await db.execute(items.insert().values(name="persisted"))

        async with db.transaction(force_rollback=True):
            await db.execute(
                items.update().where(items.c.name == "persisted").values(name="rolled-back")
            )

        value = await db.fetch_val(sqlalchemy.select(items.c.name).where(items.c.id == 1))
        assert value == "persisted"
    finally:
        await _dispose_database(db)


async def test_nested_transaction_rolls_back_inner_only(tmp_path: Path) -> None:
    db = Database(_database_url(tmp_path / "nested.db"))
    metadata = sqlalchemy.MetaData()
    items = _build_items_table(metadata)

    try:
        await db.run_sync(metadata.create_all)
        await db.execute(items.insert().values(name="initial"))

        async with db.transaction():
            await db.execute(items.update().where(items.c.id == 1).values(name="outer"))
            async with db.transaction(force_rollback=True):
                await db.execute(items.update().where(items.c.id == 1).values(name="inner"))

        value = await db.fetch_val(sqlalchemy.select(items.c.name).where(items.c.id == 1))
        assert value == "outer"
    finally:
        await _dispose_database(db)


async def test_force_rollback_root_rolls_back_on_disconnect(tmp_path: Path) -> None:
    db_path = tmp_path / "force_root.db"
    metadata = sqlalchemy.MetaData()
    items = _build_items_table(metadata)

    setup_db = Database(_database_url(db_path))
    try:
        await setup_db.run_sync(metadata.create_all)
    finally:
        await _dispose_database(setup_db)

    force_db = Database(_database_url(db_path), force_rollback=True)
    try:
        await force_db.connect()
        await force_db.execute(items.insert().values(name="temp"))
    finally:
        await force_db.disconnect()
        await force_db.dispose()

    check_db = Database(_database_url(db_path))
    try:
        count = await check_db.fetch_val(
            sqlalchemy.select(sqlalchemy.func.count()).select_from(items)
        )
        assert count == 0
    finally:
        await _dispose_database(check_db)


async def test_execute_error_rolls_back_implicit_transaction(tmp_path: Path) -> None:
    db = Database(_database_url(tmp_path / "errors.db"))
    metadata = sqlalchemy.MetaData()
    items = _build_items_table(metadata)

    try:
        await db.run_sync(metadata.create_all)
        await db.execute(items.insert().values(id=1, name="ok-1"))

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            await db.execute(items.insert().values(id=1, name="duplicate"))

        await db.execute(items.insert().values(id=2, name="ok-2"))
        count = await db.fetch_val(sqlalchemy.select(sqlalchemy.func.count()).select_from(items))
        assert count == 2
    finally:
        await _dispose_database(db)


async def test_force_rollback_context_is_task_local(tmp_path: Path) -> None:
    db = Database(_database_url(tmp_path / "contextvars.db"))
    metadata = sqlalchemy.MetaData()
    items = _build_items_table(metadata)

    try:
        await db.run_sync(metadata.create_all)
        states: list[bool] = []

        async def write_with_rollback() -> None:
            with db.force_rollback(True):
                states.append(bool(db.force_rollback))
                async with db:
                    await db.execute(items.insert().values(name="rolled"))

        async def write_without_rollback() -> None:
            await asyncio.sleep(0)
            states.append(bool(db.force_rollback))
            async with db:
                await db.execute(items.insert().values(name="saved"))

        await asyncio.gather(write_with_rollback(), write_without_rollback())

        names = [
            row._mapping["name"]
            for row in await db.fetch_all(sqlalchemy.select(items.c.name).order_by(items.c.name))
        ]
        assert sorted(states) == [False, True]
        assert names == ["saved"]
    finally:
        await _dispose_database(db)
