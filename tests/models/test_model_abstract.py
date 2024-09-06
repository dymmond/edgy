import pytest

import edgy
from edgy import Registry
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = Registry(database=database)
nother = Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
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
    async with database:
        await models.create_all()
        yield
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    async with models.database:
        yield


async def test_model_does_not_exist():
    with pytest.raises(Exception):  # noqa
        await User.query.get(name="Test", language="EN")


async def test_model_abstract():
    profile = await Profile.query.create(name="Test2", language="PT", age=23)
    contact = await Contact.query.create(
        name="Test2", language="PT", age="25", address="Westminster, London"
    )

    profiles = await Profile.query.all()
    contacts = await Contact.query.all()

    assert len(profiles) == 1
    assert len(contacts) == 1
    assert profiles[0].pk == profile.pk
    assert contacts[0].pk == contact.pk
