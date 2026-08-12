import pytest

import edgy
from edgy.core import signals
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


async def test_invalid_signal():
    broadcaster = Broadcaster()
    with pytest.raises(SignalError):
        broadcaster.save = 1


async def test_signals_simple():
    try:

        @pre_save.connect_via(User)
        async def pre_saving(sender, instance, model_instance, **kwargs):
            await Log.query.create(
                signal="pre_save", instance=model_instance.model_dump(), params=kwargs
            )

        @post_save.connect_via(User)
        async def post_saving(sender, instance, model_instance, **kwargs):
            await Log.query.create(
                signal="post_save", instance=model_instance.model_dump(), params=kwargs
            )

        @pre_update.connect_via(User)
        async def pre_updating(sender, instance, model_instance, **kwargs):
            await Log.query.create(
                signal="pre_update", instance=model_instance.model_dump(), params=kwargs
            )

        @post_update.connect_via(User)
        async def post_updating(sender, instance, model_instance, **kwargs):
            await Log.query.create(
                signal="post_update", instance=model_instance.model_dump(), params=kwargs
            )

        @pre_delete.connect_via(User)
        async def pre_deleting(sender, instance, model_instance, **kwargs):
            await Log.query.create(signal="pre_delete", instance=model_instance.model_dump())

        @post_delete.connect_via(User)
        async def post_deleting(sender, instance, model_instance, **kwargs):
            await Log.query.create(signal="post_delete", instance=model_instance.model_dump())

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
    finally:
        User.meta.signals.pre_delete.disconnect(pre_deleting)
        User.meta.signals.post_delete.disconnect(post_deleting)
        User.meta.signals.pre_save.disconnect(pre_saving)
        User.meta.signals.post_save.disconnect(post_saving)
        User.meta.signals.pre_update.disconnect(pre_updating)
        User.meta.signals.post_update.disconnect(post_updating)

    users = await User.query.all()
    assert len(users) == 1


async def test_signals_advanced():
    cleanup_array = []
    logs = await Log.query.all()
    assert len(logs) == 0
    try:
        for signal_name in dir(signals):
            if not signal_name.startswith("post_") or signal_name == "post_migrate":
                continue
            signal: signals.Signal = getattr(signals, signal_name)

            async def log(sender, model_instance, _signal_name=signal_name, **kwargs):
                await Log.query.create(
                    signal=_signal_name,
                    instance=model_instance.model_dump(),
                    params={k: str(v) for k, v in kwargs.items()},
                )

            for model in models.models.values():
                if model is not Log:
                    signal.connect(log, model, weak=False)
                    cleanup_array.append(lambda _signal=signal, _log=log: _signal.disconnect(_log))

            assert signal.has_receivers_for(User)
        # Signals for the create
        user = await User.query.create(name="Edgy")
        logs = await Log.query.all()

        assert len(logs) == 1
        assert logs[0].signal == "post_save"
        assert logs[0].instance["name"] == user.name

        user = await User.query.create(name="Saffier")
        logs = await Log.query.offset(1)

        assert len(logs) == 1
        assert logs[0].signal == "post_save"
        assert logs[0].instance["name"] == user.name

        # For the updates
        user = await user.update(name="Another Saffier")
        logs = await Log.query.filter(signal__icontains="update").all()

        assert len(logs) == 1
        assert logs[0].signal == "post_update"
        assert logs[0].instance["name"] == "Another Saffier"

        # Delete
        await user.delete()
        logs = await Log.query.filter(signal__icontains="delete").all()
        assert len(logs) == 1
        assert logs[0].signal == "post_delete"
        assert logs[0].instance["name"] == "Another Saffier"
    finally:
        for cleanup_ob in cleanup_array:
            cleanup_ob()

    users = await User.query.all()
    assert len(users) == 1
    await Log.query.delete()
    await User.query.create(name="Another Edgy")
    logs = await Log.query.all()
    assert len(logs) == 0


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
    try:
        user = await User.query.create(name="Edgy")
        await User.meta.signals.custom.send_async(User, instance=user)

        assert user.name == "Edgy ORM"
    finally:
        User.meta.signals.custom.disconnect(processing)
