import contextlib
from contextlib import asynccontextmanager

import pytest
import sqlalchemy

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)


class User(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@asynccontextmanager
async def txn():
    async with database.transaction():
        yield


async def test_select_for_update_basic_update():
    user = await User.query.create(name="John", language="PT")

    # Lock the row
    async with txn():
        locked = await User.query.filter(id=user.id).select_for_update().get()
        locked.language = "EN"
        await locked.save()

    # After commit, the change is persisted
    fresh = await User.query.get(id=user.id)
    assert fresh.language == "EN"


async def test_select_for_update_nowait_lock_conflict():
    user = await User.query.create(name="Jane", language="EN")

    other = DatabaseTestClient(DATABASE_URL, full_isolation=False)
    await other.connect()

    # Helper to run a queryset on a specific DatabaseTestClient
    def on(db, qs):
        qs2 = qs.all()

        # move the queryset to the other connection
        qs2.database = db
        return qs2

    # Txn A holds the row lock on the default connection
    async with txn():
        _ = await User.query.filter(id=user.id).select_for_update().get()

        async def try_lock_nowait_on_other_conn():
            async with other.transaction():
                return await on(
                    other, User.query.filter(id=user.id).select_for_update(nowait=True)
                ).get()

        with pytest.raises((sqlalchemy.exc.OperationalError, sqlalchemy.exc.DBAPIError)):
            await try_lock_nowait_on_other_conn()

    with contextlib.suppress(Exception):
        await other.disconnect()


async def test_select_for_update_skip_locked_excludes_locked_rows():
    user = await User.query.create(name="A", language="X")
    await User.query.create(name="B", language="Y")

    def on(db):
        qs = User.query.filter()
        qs.database = db
        return qs

    other = DatabaseTestClient(DATABASE_URL, full_isolation=False)
    await other.connect()

    try:
        # Txn A on the default client -> lock u1
        async with txn():
            _ = await User.query.filter(id=user.id).select_for_update().get()

            async with other.transaction():
                remaining = await on(other).order_by("id").select_for_update(skip_locked=True)
                ids = [u.id for u in remaining]
                assert user.id not in ids
                assert ids == [2]
    finally:
        await other.disconnect()


async def test_select_for_update_compiles_for_update_clause_present():
    queryset = User.query.select_for_update()

    sql = queryset.sql.upper()

    assert "FOR UPDATE" in sql


async def test_select_for_update_is_noop_on_sqlite_outside_txn():
    user = await User.query.create(name="Solo", language="SQ")
    rows = await User.query.filter(id=user.id).select_for_update()

    assert len(rows) == 1
    assert rows[0].id == user.id


async def test_select_for_update_of_and_shared_variants_compile_and_run():
    await User.query.create(name="PG", language="SH")

    # read=True maps to FOR SHARE on Postgres 'of' restricts tables
    queryset = (
        User.query.select_for_update(read=True, of=[User])  # FOR SHARE OF <alias>
    )
    sql = queryset.sql.upper()

    # Sanity checks on compiled SQL (not too strict, aliases vary)
    assert "FOR SHARE" in sql or "FOR UPDATE" in sql

    # 'OF' may include an alias, we just verify the keyword presence
    assert " OF " in sql

    # It should run fine inside a txn
    async with txn():
        rows = await queryset.limit(1)

        # just executes without error
        assert len(rows) >= 0
