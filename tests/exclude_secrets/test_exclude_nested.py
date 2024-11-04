import json

import pytest

import edgy
from edgy.core.utils.db import hash_tablekey
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, use_existing=False, drop_database=True)
models = edgy.Registry(database)

pytestmark = pytest.mark.anyio


class Base(edgy.StrictModel):
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
    async with models:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


async def test_exclude_secrets_excludes_top_name_equals_to_name_in_foreignkey_not_secret_query():
    profile = await Profile.query.create(is_enabled=False, name="edgy")
    user = await User.query.create(
        profile=profile, email="user@dev.com", password="dasrq3213", name="edgy"
    )
    await Organisation.query.create(user=user)

    org_query = await (
        Organisation.query.select_related("user__profile").exclude_secrets().order_by("id")
    ).as_select()
    org_query_text = str(org_query)
    assert f"{hash_tablekey(tablekey='profiles', prefix='user__profile')}_name" in org_query_text
    assert f"{hash_tablekey(tablekey='users', prefix='user')}_name" not in org_query_text


async def test_exclude_secrets_excludes_top_name_equals_to_name_in_foreignkey_not_secret():
    profile = await Profile.query.create(is_enabled=False, name="edgy")
    user = await User.query.create(
        profile=profile, email="user@dev.com", password="dasrq3213", name="edgy"
    )
    await Organisation.query.create(user=user)

    org_query = Organisation.query.select_related("user__profile").exclude_secrets().order_by("id")
    org = await org_query.last()

    assert org.model_dump() == {
        "user": {"id": 1, "profile": {"id": 1, "name": "edgy"}, "email": "user@dev.com"},
        "id": 1,
    }

    assert json.loads(org.model_dump_json()) == {
        "user": {"id": 1, "profile": {"id": 1, "name": "edgy"}, "email": "user@dev.com"},
        "id": 1,
    }
