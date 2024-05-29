import pytest

import edgy
from edgy.core.db.fields.core import Field
from edgy.exceptions import MultipleObjectsReturned, ObjectNotFound
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Product(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=100, null=True)
    rating: int = edgy.IntegerField(minimum=1, maximum=5, default=1)
    in_stock: bool = edgy.BooleanField(default=False)

    class Meta:
        registry = models
        name = "products"


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


def test_model_class():
    assert list(User.fields.keys()) == ["id", "pk", "name", "language"]
    assert isinstance(User.fields["id"], Field)
    assert User.fields["id"].primary_key is True
    assert isinstance(User.fields["name"], Field)
    assert User.fields["name"].max_length == 100

    assert User(id=1) != Product(id=1)
    assert User(id=1) != User(id=2)
    assert User(id=1) == User(id=1)

    assert str(User(id=1)) == "User(id=1)"
    assert repr(User(id=1)) == "<User: User(id=1)>"

    assert isinstance(User.query.fields["id"], Field)
    assert isinstance(User.query.fields["name"], Field)


def test_model_pk():
    user = User(pk=1)
    assert user.pk == 1
    assert user.id == 1
    assert User.query.pknames[0] == "id"


async def test_model_crud():
    users = await User.query.all()
    assert users == []

    user = await User.query.create(name="Test")
    users = await User.query.all()
    assert user.name == "Test"
    assert user.pk is not None
    assert users == [user]

    lookup = await User.query.get()
    assert lookup == user

    await user.update(name="Jane")
    users = await User.query.all()
    assert user.name == "Jane"
    assert user.pk is not None
    assert users == [user]

    await user.delete()
    users = await User.query.all()
    assert users == []


async def test_model_get():
    with pytest.raises(ObjectNotFound):
        await User.query.get()

    user = await User.query.create(name="Test")
    lookup = await User.query.get()
    assert lookup == user

    user = await User.query.create(name="Jane")
    with pytest.raises(MultipleObjectsReturned):
        await User.query.get()

    same_user = await User.query.get(pk=user.id)
    assert same_user.id == user.id
    assert same_user.pk == user.pk
