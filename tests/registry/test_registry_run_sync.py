import asyncio

import pytest

import edgy
from edgy.testing.client import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(
    DATABASE_URL,
    full_isolation=False,
    use_existing=False,
    drop_database=True,
    force_rollback=False,
)
models = edgy.Registry(database=database)


class User(edgy.StrictModel):
    name: str = edgy.fields.CharField(max_length=100)

    class Meta:
        registry = models


def test_run_sync_lifecyle():
    with models.with_async_env():
        edgy.run_sync(models.create_all())
        user = edgy.run_sync(User(name="edgy").save())
        assert user
        assert edgy.run_sync(User.query.get()) == user


def test_run_sync_lifecyle_sub():
    with models.with_async_env(), models.with_async_env():
        edgy.run_sync(models.create_all())
        user = edgy.run_sync(User(name="edgy").save())
        assert user
        assert edgy.run_sync(User.query.get()) == user


def test_run_sync_lifecyle_with_idle_loop():
    with pytest.raises(RuntimeError):
        asyncio.get_running_loop()
    loop = asyncio.new_event_loop()
    with models.with_async_env(loop=loop):
        edgy.run_sync(models.create_all())
        user = edgy.run_sync(User(name="edgy").save())
        assert user
        assert edgy.run_sync(User.query.get()) == user
    loop.close()
    with pytest.raises(RuntimeError):
        asyncio.get_running_loop()
