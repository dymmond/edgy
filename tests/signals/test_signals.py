import pytest
from loguru import logger

import edgy
from edgy.core.signals import (
    Broadcaster,
    post_delete,
    post_save,
    post_update,
    pre_delete,
    pre_save,
    pre_update,
)
from edgy.exceptions import SignalError
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Profile(edgy.Model):
    name = edgy.CharField(max_length=100)

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


def test_invalid_signal():
    broadcaster = Broadcaster()
    with pytest.raises(SignalError):
        broadcaster.save = 1


async def test_signals():
    @pre_save.connect_via(User)
    async def pre_saving(sender, instance, **kwargs):
        await Log.query.create(signal="pre_save", instance=instance.model_dump())
        logger.info(f"pre_save signal broadcasted for {instance.get_instance_name()}")

    @post_save.connect_via(User)
    async def post_saving(sender, instance, **kwargs):
        await Log.query.create(signal="post_save", instance=instance.model_dump())
        logger.info(f"post_save signal broadcasted for {instance.get_instance_name()}")

    @pre_update.connect_via(User)
    async def pre_updating(sender, instance, **kwargs):
        await Log.query.create(signal="pre_update", instance=instance.model_dump())
        logger.info(f"pre_update signal broadcasted for {instance.get_instance_name()}")

    @post_update.connect_via(User)
    async def post_updating(sender, instance, **kwargs):
        await Log.query.create(signal="post_update", instance=instance.model_dump())
        logger.info(f"post_update signal broadcasted for {instance.get_instance_name()}")

    @pre_delete.connect_via(User)
    async def pre_deleting(sender, instance, **kwargs):
        await Log.query.create(signal="pre_delete", instance=instance.model_dump())
        logger.info(f"pre_delete signal broadcasted for {instance.get_instance_name()}")

    @post_delete.connect_via(User)
    async def post_deleting(sender, instance, **kwargs):
        await Log.query.create(signal="post_delete", instance=instance.model_dump())
        logger.info(f"post_delete signal broadcasted for {instance.get_instance_name()}")

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

    # Delete
    await user.delete()
    logs = await Log.query.filter(signal__icontains="delete").all()
    assert len(logs) == 2

    user.signals.pre_delete.disconnect(pre_deleting)
    user.signals.post_delete.disconnect(post_deleting)
    user.signals.pre_save.disconnect(pre_saving)
    user.signals.post_save.disconnect(post_saving)

    users = await User.query.all()
    assert len(users) == 1


async def test_staticmethod_signals():
    class Static:
        @staticmethod
        @pre_save.connect_via(User)
        async def pre_save_one(sender, instance, **kwargs):
            await Log.query.create(signal="pre_save_one", instance=instance.model_dump_json())

        @staticmethod
        @pre_save.connect_via(User)
        async def pre_save_two(sender, instance, **kwargs):
            await Log.query.create(signal="pre_save_two", instance=instance.model_dump_json())

    # Signals for the create
    user = await User.query.create(name="Edgy")
    logs = await Log.query.all()

    assert len(logs) == 2

    user.signals.pre_save.disconnect(Static.pre_save_one)
    user.signals.pre_save.disconnect(Static.pre_save_two)


async def test_custom_signal():
    async def processing(sender, instance, **kwargs):
        instance.name = f"{instance.name} ORM"
        await instance.save()

    User.meta.signals.custom.connect(receiver=processing)

    user = await User.query.create(name="Edgy")
    await User.meta.signals.custom.send_async(User, instance=user)

    assert user.name == "Edgy ORM"

    User.meta.signals.custom.disconnect(processing)
