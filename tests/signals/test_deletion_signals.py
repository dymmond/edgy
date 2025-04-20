import pytest

import edgy
from edgy.core.signals import (
    post_delete,
    pre_delete,
)
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, drop_database=True, force_rollback=False)
models = edgy.Registry(database=database, full_isolation=False)


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    profile = edgy.ForeignKey(
        "Profile",
        null=True,
        on_delete=edgy.CASCADE,
        no_constraint=True,
        remove_referenced=True,
    )

    class Meta:
        registry = models


class Profile(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    __deletion_with_signals__ = True

    class Meta:
        registry = models


class Log(edgy.StrictModel):
    signal = edgy.CharField(max_length=255)
    is_queryset: bool = edgy.BooleanField()
    class_name: str = edgy.CharField(max_length=255)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with models:
        await models.create_all()
        yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def connect_signals():
    @pre_delete.connect_via(Profile)
    @pre_delete.connect_via(User)
    async def pre_deleting(sender, instance, model_instance, **kwargs):
        await Log.query.create(signal="pre_delete", is_queryset=model_instance is None, class_name=type(model_instance).__name__)

    @post_delete.connect_via(Profile)
    @post_delete.connect_via(User)
    async def post_deleting(sender, instance, model_instance, **kwargs):
        await Log.query.create(signal="post_delete", is_queryset=model_instance is None, class_name=type(model_instance).__name__)
    try:
        yield
    finally:
        pre_delete.disconnect(pre_deleting)
        post_delete.disconnect(post_deleting)


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
    assert logs[1].signal == "post_delete"
    assert logs[1].class_name == klass.__name__

async def test_deletion_called_once_query():
    await User.query.create(name="Edgy")
    logs = await Log.query.all()
    assert len(logs) == 0
    await User.query.delete()
    logs = await Log.query.all()
    assert len(logs) == 2
    assert logs[0].signal == "pre_delete"
    assert logs[0].class_name == type(None).__name__
    assert logs[1].signal == "post_delete"
    assert logs[1].class_name == type(None).__name__


async def test_deletion_called_referenced():
    profile = await Profile.query.create(name="Edgy")
    user = await User.query.create(name="Edgy", profile=profile)

    logs = await Log.query.all()
    assert len(logs) == 0
    await user.delete()
    logs = await Log.query.all()
    assert len(logs) == 4
    assert logs[0].signal == "pre_delete"
    assert logs[1].signal == "pre_delete"
    assert logs[2].signal == "post_delete"
    assert logs[3].signal == "post_delete"


async def test_deletion_called_cascade():
    profile = await Profile.query.create(name="Edgy")
    await User.query.create(name="Edgy", profile=profile)

    logs = await Log.query.all()
    assert len(logs) == 0
    await profile.delete()
    logs = await Log.query.all()
    assert len(logs) == 2
    assert logs[0].signal == "pre_delete"
    assert logs[1].signal == "post_delete"

async def test_deletion_called_cascade_with_signals():
    profile = await Profile.query.create(name="Edgy")
    user = await User.query.create(name="Edgy", profile=profile)

    logs = await Log.query.all()
    assert len(logs) == 0
    user.__deletion_with_signals__ = True
    await profile.delete()
    logs = await Log.query.all()
    assert len(logs) == 4
    assert logs[0].signal == "pre_delete"
    assert logs[1].signal == "pre_delete"
    assert logs[2].signal == "post_delete"
    assert logs[3].signal == "post_delete"
