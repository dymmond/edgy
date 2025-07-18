import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)
    description = edgy.TextField(max_length=5000, null=True)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


async def test_model_isnull_true():
    john = await User.query.create(name="John", description="A simple description")
    jane = await User.query.create(
        name="Jane", language="EN", description="Another simple description"
    )
    joe = await User.query.create(
        name="Joe", language="EN", description="Another simple description"
    )

    null_users = await User.query.filter(language__isnull=True).all()

    user_ids = [user.id for user in null_users]

    assert null_users[0].id == john.id
    assert jane.id not in user_ids
    assert joe.id not in user_ids


async def test_model_isnull_false():
    john = await User.query.create(name="John", description="A simple description")
    jane = await User.query.create(
        name="Jane", language="EN", description="Another simple description"
    )
    joe = await User.query.create(
        name="Joe", language="EN", description="Another simple description"
    )

    not_null_users = await User.query.filter(language__isnull=False).all()
    user_ids = [user.id for user in not_null_users]

    assert jane.id in user_ids
    assert joe.id in user_ids
    assert john.id not in user_ids
