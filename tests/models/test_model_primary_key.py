import uuid

import pytest

import edgy
from edgy import Registry
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = Registry(database=database)
nother = Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Profile(edgy.StrictModel):
    id = edgy.UUIDField(primary_key=True, default=uuid.uuid4)
    language = edgy.CharField(max_length=200, null=True)
    age = edgy.IntegerField()

    class Meta:
        registry = models
        tablename = "profiles"


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    with models.database.force_rollback():
        async with models:
            yield


async def test_model_default_primary_key():
    user = await User.query.create(name="Test", language="EN")
    users = await User.query.filter()

    assert user.pk == 1
    assert len(users) == 1


async def test_model_custom_primary_key():
    profile = await Profile.query.create(language="EN", age=18)
    profiles = await Profile.query.filter()

    assert len(profiles) == 1
    assert profiles[0].pk == profile.pk
