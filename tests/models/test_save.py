import pytest

import edgy
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Profile(edgy.Model):
    user = edgy.ForeignKey(User, related_name="profiles", on_delete=edgy.CASCADE)
    name = edgy.CharField(max_length=100)

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


async def test_model_save():
    user = await User.query.create(name="Jane")

    user.name = "John"
    await user.save()

    user = await User.query.get(pk=user.pk)

    assert user.name == "John"


async def test_model_save_simple():
    user = await User.query.create(name="Jane")

    user.name = "John"
    await user.save()

    user = await User.query.get(pk=user.pk)

    assert user.name == "John"

    total = await User.query.count()

    assert total == 1


async def test_create_model_instance():
    await User.query.create(name="edgy")

    new_user = User(name="John")
    new_user = await new_user.save()

    total = await User.query.count()

    assert total == 2

    last = await User.query.last()

    assert last.pk == new_user.pk


async def test_create_model_on_set_id_to_none():
    user = await User.query.create(name="edgy")

    user.id = None
    user.name = "John"

    # Create a new user by saving the model
    new_user = await user.save()

    total = await User.query.count()

    assert total == 2

    last = await User.query.last()

    assert last.pk == new_user.pk

    user = await User.query.get(name="edgy")

    first = await User.query.first()

    assert user.pk == first.pk


async def test_save_foreignkey_on_save():
    user = await User.query.create(name="edgy")
    profile = await Profile.query.create(user=user, name="Test")

    profile.user.name = "John"

    await profile.user.save()

    user = await User.query.first()

    assert user.name == "John"

    total = await User.query.count()

    assert total == 1
