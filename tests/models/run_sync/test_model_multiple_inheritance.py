import pytest

import edgy
from edgy import Registry
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = Registry(database=database)
nother = Registry(database=database)

pytestmark = pytest.mark.anyio


class BaseUser(edgy.Model):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        abstract = True


class Profile(BaseUser):
    age = edgy.IntegerField()

    class Meta:
        registry = models
        tablename = "profiles"


class Address(edgy.Model):
    line_one = edgy.CharField(max_length=255, null=True)
    post_code = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = models
        tablename = "addresses"


class Contact(BaseUser, Address):
    class Meta:
        registry = models
        tablename = "contacts"


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


async def test_model_inheritance():
    edgy.run_sync(Profile.query.create(name="test", language="EN", age=23))
    edgy.run_sync(Address.query.create(line_one="teste"))
    contact = edgy.run_sync(Contact.query.create(name="test2", language="AU", post_code="line"))

    profiles = edgy.run_sync(Profile.query.all())
    addresses = edgy.run_sync(Address.query.all())
    contacts = edgy.run_sync(Contact.query.all())

    assert contact.post_code == "line"
    assert len(profiles) == 1
    assert len(addresses) == 1
    assert len(contacts) == 1
