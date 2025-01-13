import pytest

import edgy
from edgy.testing import DatabaseTestClient
from edgy.testing.factory import ModelFactory
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Product(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    rating: int = edgy.IntegerField(minimum=1, maximum=5, default=1)
    in_stock: bool = edgy.BooleanField(default=False)

    class Meta:
        registry = models
        name = "products"


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


def test_can_generate_factory():
    class UserFactory(ModelFactory):
        class Meta:
            model = User

    assert UserFactory.meta.model == User
    assert UserFactory.meta.abstract is False
    assert UserFactory.meta.registry == models


def test_can_build_factory():
    class UserFactory(ModelFactory):
        class Meta:
            model = User

    user = UserFactory().build()

    assert user.database == database
