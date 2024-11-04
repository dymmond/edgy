import pytest

import edgy
from edgy import Registry
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = Registry(database=database)
nother = Registry(database=database)

pytestmark = pytest.mark.anyio


class BaseUser(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models
        abstract = True


class Profile(BaseUser):
    age = edgy.IntegerField()

    def __str__(self):
        return f"Age: {self.age}, Name:{self.name}"


class BaseUserNonAbstract(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class AnotherProfile(BaseUserNonAbstract):
    age = edgy.IntegerField()

    def __str__(self):
        return f"Age: {self.age}, Name:{self.name}"


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    async with models.database:
        yield


async def test_meta_inheritance_registry():
    await Profile.query.create(name="test", language="EN", age=23)

    await Profile.query.all()


async def test_meta_inheritance_registry_non_abstract():
    await AnotherProfile.query.create(name="test", language="EN", age=23)

    await AnotherProfile.query.all()
