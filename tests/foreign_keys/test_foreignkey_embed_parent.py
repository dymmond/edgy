
import pytest

import edgy
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = Database(DATABASE_URL)
models = edgy.Registry(database=database)



class Person(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    email = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Profile(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    website = edgy.CharField(max_length=100)

    class Meta:
        registry = models



class ProfileHolder(edgy.Model):
    profile = edgy.OneToOneField(Profile, on_delete=edgy.CASCADE, related_name=False)
    person = edgy.OneToOneField(Person, on_delete=edgy.CASCADE, embed_parent=("profile", "parent"), related_name="profile_holder")
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


async def test_embed_parent():
    profile = await Profile.query.create(website="https://edgy.com")
    person = await Person.query.create(email="info@edgy.com")
    await ProfileHolder.query.create(name="edgy", profile=profile, person=person)

    person = await Person.query.get(email="info@edgy.com")
    profile_queried = await person.profile_holder.get()
    assert profile_queried.pk == profile.pk
    assert profile_queried.website == "https://edgy.com"
    await profile_queried.parent.load()
    assert profile_queried.parent.name == "edgy"
    # try querying the embed field
    assert profile_queried.pk == (await person.profile_holder.filter(parent__name="edgy").get()).pk
