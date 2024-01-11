import pytest
from tests.settings import DATABASE_URL

import edgy
from edgy.testclient import DatabaseTestClient as Database

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


class Organisation(Base):
    user: User = edgy.ForeignKey(User)


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
    user = await User.query.create(
        profile=profile, email="user@dev.com", password="dasrq3213", name="edgy"
    )
    await Organisation.query.create(user=user)

    org = (
        await Organisation.query.select_related(["user", "user__profile"]).exclude_secrets().last()
    )

    assert org.model_dump() == {
        "user": {"id": 1, "profile": {"id": 1, "name": "edgy"}, "email": "user@dev.com"},
        "id": 1,
    }
