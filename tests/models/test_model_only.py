import pytest

import edgy
from edgy.exceptions import QuerySetError
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


async def test_raise_QuerySetError_on_only_and_defer():
    await User.query.create(name="John", language="PT", description="A simple description")

    with pytest.raises(QuerySetError):
        await User.query.only("name").defer("language")


async def test_model_only():
    john = await User.query.create(name="John", language="PT", description="A simple description")
    jane = await User.query.create(
        name="Jane", language="EN", description="Another simple description"
    )
    users = await User.query.only("name", "language")

    assert len(users) == 2
    assert [user.id for user in users] == [john.pk, jane.pk]

    john = users[0]


async def test_model_only_attribute_error():
    john = await User.query.create(name="John", language="PT")
    users = await User.query.only("name", "language")

    assert len(users) == 1
    assert users[0].pk == john.pk

    assert "description" not in john.model_dump()


async def test_model_only_with_all():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.only("name", "language").all()

    assert len(users) == 2


async def test_model_only_with_filter():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.filter(pk=1).only("name", "language")

    assert len(users) == 1

    users = await User.query.filter(id=2).only("name", "language")

    assert len(users) == 1

    users = await User.query.filter(id=2).only("name", "language").filter(id=1)

    assert len(users) == 0


async def test_model_only_with_exclude():
    await User.query.create(name="John", language="PT")
    await User.query.create(name="Jane", language="EN", description="Another simple description")

    users = await User.query.filter(pk=1).only("name", "language").exclude(id=2)

    assert len(users) == 1

    users = await User.query.filter().only("name", "language").exclude(pk=1)

    assert len(users) == 1

    users = await User.query.only("name", "language").exclude(id__in=[1, 2])

    assert len(users) == 0


async def test_model_only_save():
    await User.query.create(name="John", language="PT")

    user = await User.query.filter(pk=1).only("name", "language").get()
    user.name = "Edgy"
    user.language = "EN"
    user.description = "LOL"
    await user.save()

    user = await User.query.get(pk=1)

    assert user.name == "Edgy"
    assert user.language == "EN"


async def test_model_only_save_without_nullable_field():
    user = await User.query.create(name="John", language="PT", description="John")

    assert user.description == "John"
    assert user.language == "PT"

    user = await User.query.filter(pk=1).only("description", "language").get()
    user.language = "EN"
    user.description = "A new description"
    await user.save()

    user = await User.query.get(pk=1)

    assert user.name == "John"
    assert user.language == "EN"
    assert user.description == "A new description"
