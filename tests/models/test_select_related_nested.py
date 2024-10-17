import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, use_existing=False, drop_database=True)
models = edgy.Registry(database)

pytestmark = pytest.mark.anyio


class Base(edgy.Model):
    class Meta:
        abstract = True
        registry = models


class Profile(Base):
    name: str = edgy.CharField(max_length=1000)


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


async def test_nested_with_not_optimal_select_related_exclude_secrets():
    profile = await Profile.query.create(is_enabled=False, name="edgy")
    user = await User.query.create(
        profile=profile, email="user@dev.com", password="dasrq3213", name="edgy"
    )
    await Organisation.query.create(user=user)

    org_query = Organisation.query.exclude_secrets(True)
    # by default _select_related is a set; for having an arbitary order provide a list
    org_query._select_related = ["user", "user", "user__profile"]
    assert org_query._cached_select_related_expression is None
    org = await org_query.last()
    assert org_query._cached_select_related_expression is not None

    assert org.model_dump() == {
        "user": {"id": 1, "profile": {"id": 1, "name": "edgy"}, "email": "user@dev.com"},
        "id": 1,
    }


async def test_nested_with_not_optimal_select_related_all():
    profile = await Profile.query.create(is_enabled=False, name="edgy")
    user = await User.query.create(
        profile=profile, email="user@dev.com", password="dasrq3213", name="edgy"
    )
    await Organisation.query.create(user=user)

    org_query = Organisation.query.all()
    # by default _select_related is a set; for having an arbitary order provide a list
    org_query._select_related = ["user", "user", "user__profile"]
    assert org_query._cached_select_related_expression is None
    org = await org_query.get()
    assert org_query._cached_select_related_expression is not None

    assert org.model_dump() == {
        "user": {"id": 1, "profile": {"id": 1, "name": "edgy"}, "email": "user@dev.com"},
        "id": 1,
    }


async def test_nested_with_not_optimal_select_related_all2():
    profile = await Profile.query.create(is_enabled=False, name="edgy")
    user = await User.query.create(
        profile=profile, email="user@dev.com", password="dasrq3213", name="edgy"
    )
    await Organisation.query.create(user=user)

    org_query = Organisation.query.all()
    # by default _select_related is a set; for having an arbitary order provide a list
    org_query._select_related = ["user__profile", "user", "user"]
    assert org_query._cached_select_related_expression is None
    org = await org_query.get()
    assert org_query._cached_select_related_expression is not None

    assert org.model_dump() == {
        "user": {"id": 1, "profile": {"id": 1, "name": "edgy"}, "email": "user@dev.com"},
        "id": 1,
    }
