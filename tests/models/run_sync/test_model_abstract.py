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
        abstract = True


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
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    with models.database.force_rollback(True):
        async with models:
            yield


async def test_model_does_not_exist():
    with pytest.raises(Exception):  # noqa
        edgy.run_sync(User.query.get(name="Test", language="EN"))


async def test_model_abstract():
    profile = edgy.run_sync(Profile.query.create(name="Test2", language="PT", age=23))
    contact = edgy.run_sync(
        Contact.query.create(name="Test2", language="PT", age="25", address="Westminster, London")
    )

    profiles = edgy.run_sync(Profile.query.all())
    contacts = edgy.run_sync(Contact.query.all())

    assert len(profiles) == 1
    assert len(contacts) == 1
    assert profiles[0].pk == profile.pk
    assert contacts[0].pk == contact.pk
