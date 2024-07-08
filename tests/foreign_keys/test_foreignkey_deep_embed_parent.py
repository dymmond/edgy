
import pytest

import edgy
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = Database(DATABASE_URL)
models = edgy.Registry(database=database)


class Address(edgy.Model):
    street = edgy.CharField(max_length=100)
    city = edgy.CharField(max_length=100)


class Person(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    email = edgy.CharField(max_length=100)
    class Meta:
        registry = models


class Profile(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    website = edgy.CharField(max_length=100)
    address = Address

    class Meta:
        registry = models



class ProfileHolder(edgy.Model):
    profile = edgy.OneToOneField(Profile, on_delete=edgy.CASCADE)
    person = edgy.OneToOneField(Person, on_delete=edgy.CASCADE, embed_parent=("profile__address", "parent"), related_name="address")
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


async def test_embed_parent_deep():
    profile = await Profile.query.create(website="https://edgy.com", address={"street": "Rainbowstreet 123", "city": "London"})
    person = await Person.query.create(email="info@edgy.com")
    profile_holder = await ProfileHolder.query.create(name="edgy", profile=profile, person=person)

    person = await Person.query.get(email="info@edgy.com")
    address_queried = await person.address.get()
    assert address_queried.street == "Rainbowstreet 123"
    await address_queried.parent.load()
    assert address_queried.parent.name == profile_holder.name
    assert address_queried.parent.pk == profile_holder.pk
