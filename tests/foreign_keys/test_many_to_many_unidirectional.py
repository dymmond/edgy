import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    friends = edgy.ManyToMany("User", related_name=False)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


async def test_add_friend():
    user = await User.query.create(name="a")
    await user.friends.add(user)
    friend1 = await user.friends.create(name="b")
    friend2 = await user.friends.create(name="c")
    friend3 = await user.friends.create(name="d")
    await friend1.friends.add(friend3)
    friends = await user.friends.all()
    assert friends == [user, friend1, friend2, friend3]
    friends = await friend1.friends.all()
    assert friends == [user, friend3]
