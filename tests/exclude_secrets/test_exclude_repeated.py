import pytest

import edgy
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class Base(edgy.Model):
    class Meta:
        abstract = True
        registry = models


class Profile(Base):
    is_enabled: bool = edgy.BooleanField(default=True, secret=True)
    name: str = edgy.CharField(max_length=1000)


class User(Base):
    name: str = edgy.CharField(max_length=50, secret=True)
    email: str = edgy.EmailField(max_length=100)
    password: str = edgy.CharField(max_length=1000, secret=True)
    profile: Profile = edgy.ForeignKey(Profile, on_delete=edgy.CASCADE)


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


async def test_exclude_secrets_excludes_top_name_equals_to_name_in_foreignkey_not_secret():
    profile = await Profile.query.create(is_enabled=False, name="edgy")
    await User.query.create(
        profile=profile, email="user@dev.com", password="dasrq3213", name="edgy"
    )

    user = await User.query.select_related("profile").exclude_secrets().get()

    assert user.pk == 1
    assert user.model_dump() == {
        "profile": {"id": 1, "name": "edgy"},
        "id": 1,
        "email": "user@dev.com",
    }
