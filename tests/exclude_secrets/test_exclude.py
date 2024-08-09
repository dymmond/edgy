import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, test_prefix="")
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class Base(edgy.Model):
    class Meta:
        abstract = True
        registry = models


class Profile(Base):
    is_enabled: bool = edgy.BooleanField(default=True, secret=True)
    name: str = edgy.CharField(max_length=1000, secret=True)


class User(Base):
    name: str = edgy.CharField(max_length=50)
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


async def test_exclude_secrets_query():
    profile = await Profile.query.create(is_enabled=False, name="edgy")
    await User.query.create(
        profile=profile, email="user@dev.com", password="dasrq3213", name="edgy"
    )

    user = await User.query.exclude_secrets(id=1).get()

    assert user.pk == 1
