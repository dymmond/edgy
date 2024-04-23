import pytest

import edgy
from edgy import Registry
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
models = Registry(database=database)
nother = Registry(database=database)

pytestmark = pytest.mark.anyio


class BaseUser(edgy.Model):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models
        abstract = True


class Profile(BaseUser):
    age = edgy.IntegerField()

    def __str__(self):
        return f"Age: {self.age}, Name:{self.name}"


class BaseUserNonAbstract(edgy.Model):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class AnotherProfile(BaseUserNonAbstract):
    age = edgy.IntegerField()

    def __str__(self):
        return f"Age: {self.age}, Name:{self.name}"


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


async def test_meta_inheritance_registry():
    edgy.run_sync(Profile.query.create(name="test", language="EN", age=23))

    edgy.run_sync(Profile.query.all())


async def test_meta_inheritance_registry_non_abstract():
    edgy.run_sync(AnotherProfile.query.create(name="test", language="EN", age=23))

    edgy.run_sync(AnotherProfile.query.all())
