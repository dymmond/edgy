import pytest

import edgy
from edgy.exceptions import DatabaseNotConnectedWarning
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database))

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)
    email = edgy.EmailField(null=True, max_length=255)

    class Meta:
        registry = models


class Product(edgy.Model):
    user = edgy.ForeignKey(User, related_name="products")

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


async def test_multiple_operations():
    with pytest.warns(DatabaseNotConnectedWarning):
        await User.query.create(name="Adam", language="EN")

    query = User.query.filter()

    with pytest.warns(DatabaseNotConnectedWarning):
        await query

    with pytest.warns(DatabaseNotConnectedWarning):
        await User.query.delete()


async def test_multiple_operations_user_warning():
    with pytest.warns(UserWarning):
        await User.query.create(name="Adam", language="EN")

    query = User.query.filter()

    with pytest.warns(UserWarning):
        await query

    with pytest.warns(UserWarning):
        await User.query.delete()
