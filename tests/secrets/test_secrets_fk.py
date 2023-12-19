import datetime

import pytest
from tests.settings import DATABASE_URL

import edgy
from edgy.testclient import DatabaseTestClient as Database

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    first_name: str = edgy.CharField(max_length=255)
    last_name: str = edgy.CharField(max_length=255, secret=True)
    email: str = edgy.EmailField(max_length=255)

    class Meta:
        registry = models


class Gratitude(edgy.Model):
    owner: User = edgy.ForeignKey(User, related_name="gratitude")
    title: str = edgy.CharField(max_length=100)
    description: str = edgy.TextField()
    color: str = edgy.CharField(max_length=10, null=True)
    tags: list[str] = edgy.JSONField(default=[])
    is_visible: bool = edgy.BooleanField(default=False)
    images: list[bytes] = edgy.JSONField(default=[])
    created_at: datetime.datetime = edgy.DateTimeField(auto_now=True)
    updated_at: datetime.datetime = edgy.DateTimeField(auto_now_add=True)

    class Meta:
        registry = models


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


async def test_exclude_secrets():
    user = await User.query.create(
        first_name="Edgy",
        last_name="ORM",
        email="edgy@edgy.dev",
    )

    gratitude = await Gratitude.query.create(
        owner=user, title="test", description="A desc", color="green"
    )

    results = (
        await Gratitude.query.or_(
            owner__first_name__icontains="e",
            owner__last_name__icontains="o",
            owner__email__icontains="edgy",
            title__icontains="te",
            description__icontains="desc",
            color__icontains="green",
        )
        .exclude_secrets()
        .all()
    )
    result = results[0]

    assert len(results) == 1
    assert result.pk == gratitude.pk

    assert result.owner.model_dump() == {"id": 1, "first_name": "Edgy", "email": "edgy@edgy.dev"}
