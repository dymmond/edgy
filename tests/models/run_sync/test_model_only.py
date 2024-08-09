import pytest

import edgy
from edgy.exceptions import QuerySetError
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, test_prefix="")
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)
    description = edgy.TextField(max_length=5000, null=True)

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


async def test_raise_QuerySetError_on_only_and_defer():
    edgy.run_sync(
        User.query.create(name="John", language="PT", description="A simple description")
    )

    with pytest.raises(QuerySetError):
        edgy.run_sync(User.query.only("name").defer("language"))


async def test_model_only():
    john = edgy.run_sync(
        User.query.create(name="John", language="PT", description="A simple description")
    )
    jane = edgy.run_sync(
        User.query.create(name="Jane", language="EN", description="Another simple description")
    )
    users = edgy.run_sync(User.query.only("name", "language"))

    assert len(users) == 2
    assert [user.id for user in users] == [john.pk, jane.pk]

    john = users[0]


async def test_model_only_attribute_error():
    john = edgy.run_sync(User.query.create(name="John", language="PT"))
    users = edgy.run_sync(User.query.only("name", "language"))

    assert len(users) == 1
    assert users[0].pk == john.pk

    assert "description" not in john.model_dump()


async def test_model_only_with_all():
    edgy.run_sync(User.query.create(name="John", language="PT"))
    edgy.run_sync(
        User.query.create(name="Jane", language="EN", description="Another simple description")
    )

    users = edgy.run_sync(User.query.only("name", "language").all())

    assert len(users) == 2


async def test_model_only_with_filter():
    edgy.run_sync(User.query.create(name="John", language="PT"))
    edgy.run_sync(
        User.query.create(name="Jane", language="EN", description="Another simple description")
    )

    users = edgy.run_sync(User.query.filter(pk=1).only("name", "language"))

    assert len(users) == 1

    users = edgy.run_sync(User.query.filter(id=2).only("name", "language"))

    assert len(users) == 1

    users = edgy.run_sync(User.query.filter(id=2).only("name", "language").filter(id=1))

    assert len(users) == 0


async def test_model_only_with_exclude():
    edgy.run_sync(User.query.create(name="John", language="PT"))
    edgy.run_sync(
        User.query.create(name="Jane", language="EN", description="Another simple description")
    )

    users = edgy.run_sync(User.query.filter(pk=1).only("name", "language").exclude(id=2))

    assert len(users) == 1

    users = edgy.run_sync(User.query.filter().only("name", "language").exclude(pk=1))

    assert len(users) == 1

    users = edgy.run_sync(User.query.only("name", "language").exclude(id__in=[1, 2]))

    assert len(users) == 0


async def test_model_only_save():
    edgy.run_sync(User.query.create(name="John", language="PT"))

    user = edgy.run_sync(User.query.filter(pk=1).only("name", "language").get())
    user.name = "Edgy"
    user.language = "EN"
    user.description = "LOL"
    edgy.run_sync(user.save())

    user = edgy.run_sync(User.query.get(pk=1))

    assert user.name == "Edgy"
    assert user.language == "EN"


async def test_model_only_save_without_nullable_field():
    user = edgy.run_sync(User.query.create(name="John", language="PT", description="John"))

    assert user.description == "John"
    assert user.language == "PT"

    user = edgy.run_sync(User.query.filter(pk=1).only("description", "language").get())
    user.language = "EN"
    user.description = "A new description"
    edgy.run_sync(user.save())

    user = edgy.run_sync(User.query.get(pk=1))

    assert user.name == "John"
    assert user.language == "EN"
    assert user.description == "A new description"
