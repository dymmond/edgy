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


class Profile(User):
    age = edgy.IntegerField()

    class Meta:
        registry = models
        tablename = "profiles"


class Contact(Profile):
    age = edgy.CharField(max_length=255)
    address = edgy.CharField(max_length=255)

    class Meta:
        registry = models
        tablename = "contacts"


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    # this creates and drops the database
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    # this rolls back
    async with models:
        yield


async def test_model_inheritance():
    user = edgy.run_sync(User.query.create(name="Test", language="EN"))
    profile = edgy.run_sync(Profile.query.create(name="Test2", language="PT", age=23))

    users = edgy.run_sync(User.query.all())
    profiles = edgy.run_sync(Profile.query.all())

    assert len(users) == 1
    assert len(profiles) == 1
    assert users[0].pk == user.pk
    assert profiles[0].pk == profile.pk


async def test_model_triple_inheritace():
    contact = edgy.run_sync(
        Contact.query.create(name="Test", language="EN", age="25", address="Far")
    )

    contacts = edgy.run_sync(Contact.query.all())

    assert len(contacts) == 1
    assert contact.age == "25"
    assert contact.address == "Far"
