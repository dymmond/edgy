import asyncio
import gc
import time

import pytest

import edgy
from edgy.core.utils.sync import weak_subloop_map
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


async def check_is_value(value):
    assert len(weak_subloop_map) == value


async def check_is_value_sub(value):
    edgy.run_sync(check_is_value(value + 1))


def test_stack():
    gc.collect()
    time.sleep(1)

    initial = len(weak_subloop_map)
    loop = asyncio.new_event_loop()
    with models.with_async_env(loop):
        assert initial == len(weak_subloop_map)
        edgy.run_sync(check_is_value(initial))
        edgy.run_sync(check_is_value_sub(initial))
    loop.close()
    del loop
    gc.collect()
    time.sleep(1)
    assert initial == len(weak_subloop_map)
