from typing import cast

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


class User(edgy.StrictModel):
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
        registry = models
        signals = {"pre_delete": Signal()}


class Profile(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    __deletion_with_signals__ = True

    class Meta:
        registry = models
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
    @Profile.meta.signals.pre_delete.connect_via(Profile, weak=True)
    @User.meta.signals.pre_delete.connect_via(User, weak=True)
    async def pre_deleting(sender, **kwargs):
        await Log.query.create(
            signal="pre_delete",
            class_name=sender.__name__,
            params={k: str(v) for k, v in kwargs.items()},
        )

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
        Profile.meta.signals.pre_delete.disconnect(pre_deleting)
        User.meta.signals.pre_delete.disconnect(pre_deleting)
        Profile.meta.signals.post_delete.disconnect(post_deleting)
        User.meta.signals.post_delete.disconnect(post_deleting)


@pytest.mark.parametrize("klass", [User, Profile])
async def test_correct_connection(klass):
    assert klass.meta.signals.pre_delete is not pre_delete
    assert klass.meta.signals.post_delete is post_delete
    assert not pre_delete.has_receivers_for(klass)
    assert klass.meta.signals.pre_delete.has_receivers_for(klass)
    assert post_delete.has_receivers_for(klass)


@pytest.mark.parametrize("klass", [User, Profile])
async def test_deletion_called_once_model(klass):
    obj = await klass.query.create(name="Edgy")
    logs = await Log.query.all()
    assert len(logs) == 0
    await obj.delete()
    logs = await Log.query.all()
    assert len(logs) == 2
    assert logs[0].signal == "pre_delete"
    assert logs[0].class_name == klass.__name__
    assert logs[0].params["instance"].startswith(f"{klass.__name__}")
    assert logs[0].params["model_instance"].startswith(f"{klass.__name__}")
    assert "row_count" not in logs[0].params
    assert logs[1].signal == "post_delete"
    assert logs[1].class_name == klass.__name__
    assert logs[1].params["instance"].startswith(f"{klass.__name__}")
    assert logs[1].params["model_instance"].startswith(f"{klass.__name__}")
    assert logs[1].params["row_count"] == "1"


@pytest.mark.parametrize("klass", [User, Profile])
async def test_deletion_called_once_query(klass):
    await klass.query.create(name="Edgy")
    logs = await Log.query.all()
    assert len(logs) == 0
    await klass.query.delete()
    logs = await Log.query.all()
    if klass.__deletion_with_signals__:
        assert len(logs) == 4
        assert logs[0].signal == "pre_delete"
        assert logs[0].class_name == klass.__name__
        assert logs[0].params["instance"].startswith(f"QuerySet<for <{klass.__name__}>")
        assert logs[0].params["model_instance"] == "None"
        assert "row_count" not in logs[0].params
        assert logs[1].signal == "pre_delete"
        assert logs[2].params["instance"].startswith(f"QuerySet<for <{klass.__name__}>")
        assert logs[1].params["model_instance"].startswith(f"{klass.__name__}")
        assert "row_count" not in logs[0].params
        assert logs[2].signal == "post_delete"
        assert logs[2].class_name == klass.__name__
        assert logs[2].params["instance"].startswith(f"QuerySet<for <{klass.__name__}>")
        assert logs[2].params["model_instance"].startswith(f"{klass.__name__}")
        assert logs[2].params["row_count"] == "1"
        assert logs[3].signal == "post_delete"
        assert logs[3].class_name == klass.__name__
        assert logs[3].params["instance"].startswith(f"QuerySet<for <{klass.__name__}>")
        assert logs[3].params["model_instance"] == "None"
        assert logs[3].params["row_count"] == "1"

    else:
        assert len(logs) == 2
        assert logs[0].signal == "pre_delete"
        assert logs[0].class_name == klass.__name__
        assert logs[0].params["instance"].startswith(f"QuerySet<for <{klass.__name__}>")
        assert logs[0].params["model_instance"] == "None"
        assert "row_count" not in logs[0].params
        assert logs[1].signal == "post_delete"
        assert logs[1].class_name == klass.__name__
        assert logs[1].params["instance"].startswith(f"QuerySet<for <{klass.__name__}>")
        assert logs[1].params["model_instance"] == "None"
        assert logs[1].params["row_count"] == "1"


async def test_deletion_called_referenced():
    profile = await Profile.query.create(name="Edgy")
    user = await User.query.create(name="Edgy", profile=profile)

    logs = await Log.query.all()
    assert len(logs) == 0
    await user.delete()
    logs = await Log.query.all()
    assert len(logs) == 4
    assert logs[0].signal == "pre_delete"
    assert logs[0].class_name == "User"
    assert logs[1].signal == "pre_delete"
    assert logs[1].class_name == "Profile"
    assert logs[2].signal == "post_delete"
    assert logs[2].class_name == "Profile"
    assert logs[3].signal == "post_delete"
    assert logs[3].class_name == "User"


async def test_deletion_called_cascade():
    profile = await Profile.query.create(name="Edgy")
    await User.query.create(name="Edgy", profile=profile)
    await User.query.create(name="Edgy2", profile=profile)

    logs = await Log.query.all()
    assert len(logs) == 0
    await profile.delete()
    logs = await Log.query.all()
    assert len(logs) == 2
    assert logs[0].signal == "pre_delete"
    assert logs[0].class_name == "Profile"
    assert logs[1].signal == "post_delete"
    assert logs[1].class_name == "Profile"


async def test_deletion_called_cascade_with_signals():
    profile = await Profile.query.create(name="Edgy")
    await User.query.create(name="Edgy", profile=profile)
    await User.query.create(name="Edgy2", profile=profile)

    logs = await Log.query.all()
    assert len(logs) == 0
    User.__deletion_with_signals__ = True
    await profile.delete()
    User.__deletion_with_signals__ = False
    logs = await Log.query.all()
    assert len(logs) == 6
    assert logs[0].signal == "pre_delete"
    assert logs[0].class_name == "Profile"
    assert logs[1].signal == "pre_delete"
    assert logs[1].class_name == "User"
    assert logs[2].signal == "post_delete"
    assert logs[2].class_name == "User"
    assert logs[3].signal == "pre_delete"
    assert logs[3].class_name == "User"
    assert logs[4].signal == "post_delete"
    assert logs[4].class_name == "User"
    assert logs[5].signal == "post_delete"
    assert logs[5].class_name == "Profile"


async def test_model_base_deletion_with_skip():
    queryset = Profile.query.batch_size(2)

    @Profile.meta.signals.pre_delete.connect_via(Profile, weak=True)
    async def pre_deleting(sender, instance, model_instance, **kwargs):
        assert instance is queryset
        if model_instance and model_instance.name.startswith("raise"):
            raise SkipOperation()

    try:
        await queryset.create(name="raise Edgy")
        await queryset.create(name="noraise Edgy")
        await queryset.create(name="raise Saffier")
        await queryset.create(name="noraise Saffier")
        assert bool(queryset._cache)
        await queryset
        # now everything is fetched
        assert queryset._cache_fetch_all
        await queryset.delete()
    finally:
        Profile.meta.signals.pre_delete.disconnect(pre_deleting)
    assert not queryset._cache.cache
    assert queryset._cache_count is None
    assert queryset._cache_first is None
    assert queryset._cache_last is None
    # prevent confused type checkers
    assert not cast(bool, queryset._cache_fetch_all)
    assert await queryset.count() == 2
    assert await Profile.query.count() == 2
