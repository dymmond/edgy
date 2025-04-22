import pytest
import sqlalchemy
from sqlalchemy import exc

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class User(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=255)
    is_admin = edgy.fields.BooleanField(default=False)
    age = edgy.IntegerField(null=True)

    class Meta:
        registry = models
        constraints = [sqlalchemy.CheckConstraint("age > 13 OR is_admin = true", name="user_age")]


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    # this creates and drops the database
    async with database:
        await models.create_all()
        yield
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    # this rolls back
    async with models:
        yield


async def test_create_user():
    user = await User.query.create(name="Test", is_admin=False, age=20)
    assert user.age == 20


async def test_create_admin():
    user = await User.query.create(name="Test", is_admin=True)
    assert user.age is None


async def test_fail_create_user():
    with pytest.raises(exc.IntegrityError):
        await User.query.create(name="Test", is_admin=False, age=1)
