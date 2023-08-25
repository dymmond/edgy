import pytest
from loguru import logger
from tests.settings import DATABASE_URL

import edgy
from edgy.core.signals import (
    Broadcaster,
    post_bulk_update,
    post_delete,
    post_save,
    post_update,
    pre_delete,
    pre_save,
    pre_update,
)
from edgy.exceptions import SignalError
from edgy.testclient import DatabaseTestClient as Database

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Log(edgy.Model):
    signal = edgy.CharField(max_length=255)
    instance = edgy.JSONField()

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


@pytest.mark.parametrize("func", ["bad", 1, 3, [3], {"name": "test"}])
def test_passing_not_callable(func):
    with pytest.raises(SignalError):
        pre_save(User)(func)


def test_passing_no_kwargs():
    with pytest.raises(SignalError):

        @pre_save(User)
        def execute(sender, instance):
            ...


def test_invalid_signal():
    broadcaster = Broadcaster()
    with pytest.raises(SignalError):
        broadcaster.save = 1


async def test_signals():
    @pre_save(User)
    async def pre_saving(sender, instance, **kwargs):
        await Log.query.create(signal="pre_save", instance=instance.model_dump())
        logger.info(f"pre_save signal broadcasted for {instance.get_instance_name()}")

    @post_save(User)
    async def post_saving(sender, instance, **kwargs):
        await Log.query.create(signal="post_save", instance=instance.model_dump())
        logger.info(f"post_save signal broadcasted for {instance.get_instance_name()}")

    @pre_update(User)
    async def pre_updating(sender, instance, **kwargs):
        await Log.query.create(signal="pre_update", instance=instance.model_dump())
        logger.info(f"pre_update signal broadcasted for {instance.get_instance_name()}")

    @post_update(User)
    async def post_updating(sender, instance, **kwargs):
        await Log.query.create(signal="post_update", instance=instance.model_dump())
        logger.info(f"post_update signal broadcasted for {instance.get_instance_name()}")

    @pre_delete(User)
    async def pre_deleting(sender, instance, **kwargs):
        await Log.query.create(signal="pre_delete", instance=instance.model_dump())
        logger.info(f"pre_delete signal broadcasted for {instance.get_instance_name()}")

    @post_delete(User)
    async def post_deleting(sender, instance, **kwargs):
        await Log.query.create(signal="post_delete", instance=instance.model_dump())
        logger.info(f"post_delete signal broadcasted for {instance.get_instance_name()}")

    @post_bulk_update(User)
    async def post_bulk_updating(sender, instances, **kwargs):
        for instance in instances:
            await Log.query.create(signal="post_bulk_update", instance=instance.model_dump())
        logger.info(f"post_bulk_update signal broadcasted for {instance.get_instance_name()}")

    # Signals for the create
    user = await User.query.create(name="Edgy")
    logs = await Log.query.all()

    assert len(logs) == 2
    assert logs[0].signal == "pre_save"
    assert logs[0].instance["name"] == user.name
    assert logs[1].signal == "post_save"

    user = await User.query.create(name="Saffier")
    logs = await Log.query.all()

    assert len(logs) == 4
    assert logs[2].signal == "pre_save"
    assert logs[2].instance["name"] == user.name
    assert logs[3].signal == "post_save"

    # For the updates
    user = await user.update(name="Another Saffier")
    logs = await Log.query.filter(signal__icontains="update").all()

    assert len(logs) == 2
    assert logs[0].signal == "pre_update"
    assert logs[0].instance["name"] == "Saffier"
    assert logs[1].signal == "post_update"

    user.signals.pre_update.disconnect(pre_updating)
    user.signals.post_update.disconnect(post_updating)

    # Disconnect the signals
    user = await user.update(name="Saffier")
    logs = await Log.query.filter(signal__icontains="update").all()
    assert len(logs) == 2
