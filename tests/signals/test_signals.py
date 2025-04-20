import pytest

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
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=database, full_isolation=False)

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Profile(edgy.StrictModel):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Log(edgy.StrictModel):
    signal = edgy.CharField(max_length=255)
    instance = edgy.JSONField()
    params = edgy.JSONField(default={})

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


def test_invalid_signal():
    broadcaster = Broadcaster()
    with pytest.raises(SignalError):
        broadcaster.save = 1


async def test_signals():
    @pre_save.connect_via(User)
    async def pre_saving(sender, instance, model_instance, **kwargs):
        await Log.query.create(
            signal="pre_save", instance=model_instance.model_dump(), params=kwargs
        )
        print(f"pre_save signal broadcasted for {model_instance.get_instance_name()}")

    @post_save.connect_via(User)
    async def post_saving(sender, instance, model_instance, **kwargs):
        await Log.query.create(
            signal="post_save", instance=model_instance.model_dump(), params=kwargs
        )
        print(f"post_save signal broadcasted for {model_instance.get_instance_name()}")

    @pre_update.connect_via(User)
    async def pre_updating(sender, instance, model_instance, **kwargs):
        await Log.query.create(
            signal="pre_update", instance=model_instance.model_dump(), params=kwargs
        )
        print(f"pre_update signal broadcasted for {model_instance.get_instance_name()}")

    @post_update.connect_via(User)
    async def post_updating(sender, instance, model_instance, **kwargs):
        await Log.query.create(
            signal="post_update", instance=model_instance.model_dump(), params=kwargs
        )
        print(f"post_update signal broadcasted for {model_instance.get_instance_name()}")

    @pre_delete.connect_via(User)
    async def pre_deleting(sender, instance, model_instance, **kwargs):
        await Log.query.create(signal="pre_delete", instance=model_instance.model_dump())
        print(f"pre_delete signal broadcasted for {model_instance.get_instance_name()}")

    @post_delete.connect_via(User)
    async def post_deleting(sender, instance, model_instance, **kwargs):
        await Log.query.create(signal="post_delete", instance=model_instance.model_dump())
        print(f"post_delete signal broadcasted for {model_instance.get_instance_name()}")

    # Signals for the create
    user = await User.query.create(name="Edgy")
    logs = await Log.query.all()

    assert len(logs) == 2
    assert logs[0].signal == "pre_save"
    assert logs[0].instance["name"] == user.name
    assert logs[1].signal == "post_save"

    user = await User.query.create(name="Saffier")
    logs = await Log.query.offset(2)

    assert len(logs) == 2
    assert logs[0].signal == "pre_save"
    assert logs[0].instance["name"] == user.name
    assert logs[1].signal == "post_save"

    # For the updates
    user = await user.update(name="Another Saffier")
    logs = await Log.query.filter(signal__icontains="update").all()

    assert len(logs) == 2
    assert logs[0].signal == "pre_update"
    assert logs[0].instance["name"] == "Saffier"
    assert logs[1].signal == "post_update"

    user.meta.signals.pre_update.disconnect(pre_updating)
    user.meta.signals.post_update.disconnect(post_updating)

    # Disconnect the signals
    user = await user.update(name="Saffier")
    logs = await Log.query.filter(signal__icontains="update").all()
    assert len(logs) == 2

    # Delete
    await user.delete()
    logs = await Log.query.filter(signal__icontains="delete").all()
    assert len(logs) == 2

    user.meta.signals.pre_delete.disconnect(pre_deleting)
    user.meta.signals.post_delete.disconnect(post_deleting)
    user.meta.signals.pre_save.disconnect(pre_saving)
    user.meta.signals.post_save.disconnect(post_saving)
    user.meta.signals.pre_update.disconnect(pre_updating)
    user.meta.signals.post_update.disconnect(post_updating)

    users = await User.query.all()
    assert len(users) == 1


async def test_staticmethod_signals():
    class Static:
        @staticmethod
        @pre_save.connect_via(User)
        async def pre_save_one(sender, model_instance, **kwargs):
            await Log.query.create(
                signal="pre_save_one", instance=model_instance.model_dump_json()
            )

        @staticmethod
        @pre_save.connect_via(User)
        async def pre_save_two(sender, model_instance, **kwargs):
            await Log.query.create(
                signal="pre_save_two", instance=model_instance.model_dump_json()
            )

    # Signals for the create
    user = await User.query.create(name="Edgy")
    logs = await Log.query.all()

    assert len(logs) == 2

    user.meta.signals.pre_save.disconnect(Static.pre_save_one)
    user.meta.signals.pre_save.disconnect(Static.pre_save_two)


async def test_custom_signal():
    async def processing(sender, instance, **kwargs):
        instance.name = f"{instance.name} ORM"
        await instance.save()

    User.meta.signals.custom.connect(receiver=processing)

    user = await User.query.create(name="Edgy")
    await User.meta.signals.custom.send_async(User, instance=user)

    assert user.name == "Edgy ORM"

    User.meta.signals.custom.disconnect(processing)
