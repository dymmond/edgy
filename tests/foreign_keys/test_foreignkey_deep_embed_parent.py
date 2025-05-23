import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database))


class Address(edgy.StrictModel):
    street = edgy.CharField(max_length=100)
    city = edgy.CharField(max_length=100)


class Person(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    email = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Profile(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    website = edgy.CharField(max_length=100)
    address = Address

    class Meta:
        registry = models


class ProfileHolder(edgy.StrictModel):
    profile = edgy.OneToOneField(Profile, on_delete=edgy.CASCADE)
    person = edgy.OneToOneField(
        Person,
        on_delete=edgy.CASCADE,
        embed_parent=("profile__address", "parent"),
        related_name="address",
    )
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


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


async def test_embed_parent_deep():
    profile = await Profile.query.create(
        website="https://edgy.com", address={"street": "Rainbowstreet 123", "city": "London"}
    )
    person = await Person.query.create(email="info@edgy.com")
    profile_holder = await ProfileHolder.query.create(name="edgy", profile=profile, person=person)

    person = await Person.query.get(email="info@edgy.com")
    address_queried = await person.address.get()
    assert address_queried.street == "Rainbowstreet 123"
    await address_queried.parent.load()
    assert address_queried.parent.name == profile_holder.name
    assert address_queried.parent.pk == profile_holder.pk
