import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, use_existing=False, drop_database=True)
models = edgy.Registry(database)

pytestmark = pytest.mark.anyio


class Base(edgy.StrictModel):
    class Meta:
        abstract = True
        registry = models


def callback(field, model_instance, model_owner):
    # for implementing secret
    if field.name in model_instance.__no_load_trigger_attrs__:
        raise AttributeError
    return "foo"


class Profile(Base):
    name: str = edgy.CharField(max_length=1000)
    # by default excluded
    computed = edgy.fields.ComputedField(callback, exclude=False, secret=True)


class User(Base):
    id = edgy.fields.BigIntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=50, exclude=True)
    email: str = edgy.EmailField(max_length=100)
    password: str = edgy.CharField(max_length=1000, exclude=True)
    profile: Profile = edgy.ForeignKey(Profile, on_delete=edgy.CASCADE)


class Organisation(Base):
    user: User = edgy.ForeignKey(User)


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with models:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


async def test_nested_defer():
    profile = await Profile.query.create(name="edgy")
    user = await User.query.create(
        profile=profile, email="user@dev.com", password="dasrq3213", name="edgy"
    )
    await Organisation.query.create(user=user)

    org_query = Organisation.query.select_related("user__profile").defer("name")
    org = await org_query.last()

    assert org.model_dump() == {
        "user": {
            "id": 1,
            "profile": {"id": 1, "name": "edgy", "computed": "foo"},
            "email": "user@dev.com",
        },
        "id": 1,
    }


async def test_nested_exclude_secret():
    profile = await Profile.query.create(name="edgy")
    user = await User.query.create(
        profile=profile, email="user@dev.com", password="dasrq3213", name="edgy"
    )
    await Organisation.query.create(user=user)

    org_query = Organisation.query.select_related("user__profile").exclude_secrets(True)
    org = await org_query.last()

    assert org.model_dump() == {
        "user": {
            "id": 1,
            "profile": {"id": 1, "name": "edgy"},
            "email": "user@dev.com",
        },
        "id": 1,
    }
