import pytest

import edgy
from edgy.core.signals import Signal, post_delete, pre_delete
from edgy.exceptions import SkipOperation
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(
    DATABASE_URL, drop_database=True, force_rollback=False, full_isolation=False
)
models = edgy.Registry(database=database)


class BaseModelWithDeletionHandling(edgy.StrictModel):
    protection = edgy.BooleanField(default=True)

    class Meta:
        registry = models
        abstract = True


class Unrelated(BaseModelWithDeletionHandling):
    name = edgy.CharField(max_length=100)


class User(BaseModelWithDeletionHandling):
    name = edgy.CharField(max_length=100)
    profile = edgy.ForeignKey(
        "Profile",
        null=True,
        on_delete=edgy.CASCADE,
        no_constraint=True,
        remove_referenced=True,
        use_model_based_deletion=True,
    )

    class Meta:
        signals = {"pre_delete": Signal()}


class Profile(BaseModelWithDeletionHandling):
    name = edgy.CharField(max_length=100)
    __deletion_with_signals__ = True

    class Meta:
        signals = {"pre_delete": Signal()}


class Log(edgy.StrictModel):
    signal = edgy.CharField(max_length=255)
    class_name = edgy.CharField(max_length=255)
    params = edgy.JSONField()

    class Meta:
        registry = models

    def __str__(self) -> str:
        return str(self.extract_db_fields())

    def __repr__(self) -> str:
        return f"Log<{self}>"


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with models:
        await models.create_all()
        yield


@pytest.fixture(autouse=True, scope="function")
async def connect_signals():
    @Unrelated.meta.signals.pre_delete.connect_via(Unrelated, weak=True)
    @Profile.meta.signals.pre_delete.connect_via(Profile, weak=True)
    @User.meta.signals.pre_delete.connect_via(User, weak=True)
    async def pre_deleting(sender, model_instance, injected_filters=None, **kwargs):
        if model_instance is not None:
            if model_instance.protection:
                raise SkipOperation()
        elif injected_filters is not None:
            injected_filters.append({"protection": False})

    @Unrelated.meta.signals.post_delete.connect_via(Unrelated, weak=True)
    @Profile.meta.signals.post_delete.connect_via(Profile, weak=True)
    @User.meta.signals.post_delete.connect_via(User, weak=True)
    async def post_deleting(sender, **kwargs):
        await Log.query.create(
            signal="post_delete",
            class_name=sender.__name__,
            params={k: str(v) for k, v in kwargs.items()},
        )

    try:
        yield
    finally:
        Unrelated.meta.signals.pre_delete.disconnect(pre_deleting)
        Profile.meta.signals.pre_delete.disconnect(pre_deleting)
        User.meta.signals.pre_delete.disconnect(pre_deleting)
        Unrelated.meta.signals.post_delete.disconnect(pre_deleting)
        Profile.meta.signals.post_delete.disconnect(post_deleting)
        User.meta.signals.post_delete.disconnect(post_deleting)


@pytest.mark.parametrize("klass", [User, Profile])
async def test_correct_connection(klass):
    assert klass.meta.signals.pre_delete is not pre_delete
    assert klass.meta.signals.post_delete is post_delete
    assert not pre_delete.has_receivers_for(klass)
    assert klass.meta.signals.pre_delete.has_receivers_for(klass)
    assert post_delete.has_receivers_for(klass)


@pytest.mark.parametrize("klass", [User, Profile, Unrelated])
async def test_deletion_called_once_model(klass):
    obj = await klass.query.create(name="Edgy")
    assert not obj._db_deleted
    logs = await Log.query.all()
    assert len(logs) == 0
    await obj.delete()
    assert not obj._db_deleted
    assert await klass.query.count() == 1
    logs = await Log.query.all()
    assert len(logs) == 1
    assert logs[0].signal == "post_delete"
    assert logs[0].class_name == klass.__name__
    assert logs[0].params["model_instance"] != "None"
    assert logs[0].params["row_count"] == "0"


@pytest.mark.parametrize("klass", [User, Profile, Unrelated])
@pytest.mark.parametrize("model_based", [True, False])
async def test_deletion_called_once_query(klass, model_based):
    await klass.query.create(name="Edgy")
    logs = await Log.query.all()
    assert len(logs) == 0
    await klass.query.delete(model_based)
    assert await klass.query.count() == 1
    logs = await Log.query.all()
    assert len(logs) == 1
    assert logs[0].signal == "post_delete"
    assert logs[0].class_name == klass.__name__
    assert logs[0].params["instance"].startswith(f"QuerySet<for <{klass.__name__}>")
    assert logs[0].params["model_instance"] == "None"
    assert logs[0].params["row_count"] == "0"


@pytest.mark.parametrize("klass", [User, Profile])
async def test_deletion_called_once_query_model_based(klass):
    await klass.query.create(name="Edgy")
    logs = await Log.query.all()
    assert len(logs) == 0
    await klass.query.delete()
    logs = await Log.query.all()
    assert await klass.query.count() == 1
    assert len(logs) == 1
    assert logs[0].signal == "post_delete"
    assert logs[0].class_name == klass.__name__
    assert logs[0].params["instance"].startswith(f"QuerySet<for <{klass.__name__}>")
    assert logs[0].params["model_instance"] == "None"
    assert logs[0].params["row_count"] == "0"


async def test_deletion_called_referenced():
    user = await User.query.create(name="Edgy", profile=Profile(name="Edgy"))
    logs = await Log.query.all()
    assert len(logs) == 0
    await user.delete()
    logs = await Log.query.all()
    assert len(logs) == 1
    assert logs[0].class_name == "User"
    assert logs[0].signal == "post_delete"
    assert logs[0].params["row_count"] == "0"
    assert logs[0].params["operation_skipped"] == "True"
    # now it really deletes
    with User.meta.signals.pre_delete.muted():
        await user.delete()
    logs = await Log.query.offset(1)
    assert len(logs) == 2
    assert logs[0].class_name == "Profile"
    assert logs[0].signal == "post_delete"
    assert logs[0].params["row_count"] == "0"
    assert logs[0].params["operation_skipped"] == "True"
    assert logs[0].params["model_instance"] != "None"

    assert logs[1].class_name == "User"
    assert logs[1].signal == "post_delete"
    assert logs[1].params["row_count"] == "1"
    assert logs[1].params["model_instance"] != "None"
    assert logs[1].params["operation_skipped"] == "False"


async def test_deletion_called_referenced_query():
    await User.query.create(name="Edgy", profile=Profile(name="Edgy"))
    logs = await Log.query.all()
    assert len(logs) == 0
    await User.query.delete()
    logs = await Log.query.all()
    assert len(logs) == 1
    assert logs[0].class_name == "User"
    assert logs[0].signal == "post_delete"
    assert logs[0].params["row_count"] == "0"
    assert logs[0].params["operation_skipped"] == "False"
    assert await User.query.count() == 1
    # now it really deletes
    with User.meta.signals.pre_delete.muted():
        await User.query.delete()
    assert await User.query.count() == 0
    logs = await Log.query.offset(1)
    assert len(logs) == 2

    assert logs[0].class_name == "Profile"
    assert logs[0].signal == "post_delete"
    assert logs[0].params["row_count"] == "0"
    assert logs[0].params["operation_skipped"] == "True"
    assert logs[0].params["model_instance"] != "None"

    assert logs[1].class_name == "User"
    assert logs[1].signal == "post_delete"
    assert logs[1].params["row_count"] == "1"
    assert logs[1].params["model_instance"] == "None"
    assert logs[1].params["operation_skipped"] == "False"


async def test_deletion_called_cascade():
    profile = await Profile.query.create(name="Edgy")
    await User.query.create(name="Edgy", profile=profile)
    await User.query.create(name="Edgy2", profile=profile)
    logs = await Log.query.all()
    assert len(logs) == 0
    await profile.delete()
    logs = await Log.query.all()
    assert len(logs) == 1
    assert logs[0].class_name == "Profile"
    assert logs[0].signal == "post_delete"
    assert logs[0].params["row_count"] == "0"
    assert logs[0].params["operation_skipped"] == "True"
    # now it really deletes
    with Profile.meta.signals.pre_delete.muted():
        await profile.delete()
    logs = await Log.query.offset(1)
    assert len(logs) == 1
    assert logs[0].class_name == "Profile"
    assert logs[0].signal == "post_delete"
    assert logs[0].params["row_count"] == "1"
    assert logs[0].params["operation_skipped"] == "False"
    assert logs[0].params["model_instance"] != "None"


async def test_deletion_called_cascade_query():
    profile = await Profile.query.create(name="Edgy")
    await User.query.create(name="Edgy", profile=profile)
    await User.query.create(name="Edgy2", profile=profile)
    logs = await Log.query.all()
    assert len(logs) == 0
    await Profile.query.delete()
    logs = await Log.query.all()
    assert len(logs) == 1
    assert logs[0].class_name == "Profile"
    assert logs[0].signal == "post_delete"
    assert logs[0].params["row_count"] == "0"
    # now it really deletes
    with Profile.meta.signals.pre_delete.muted():
        await Profile.query.delete()
    logs = await Log.query.offset(1)
    assert len(logs) == 2
    assert logs[0].class_name == "Profile"
    assert logs[0].signal == "post_delete"
    assert logs[0].params["row_count"] == "1"
    assert logs[1].class_name == "Profile"
    assert logs[1].signal == "post_delete"
    assert logs[1].params["row_count"] == "1"
