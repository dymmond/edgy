import pytest

import edgy
from edgy.core.db.fields.base import Field
from edgy.exceptions import MultipleObjectsReturned, ObjectNotFound
from edgy.testclient import DatabaseTestClient
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


def test_model_class():
    assert sorted(User.meta.fields.keys()) == sorted(["pk", "id", "name", "language"])
    assert isinstance(User.meta.fields["id"], Field)
    assert User.meta.fields["id"].primary_key is True
    assert isinstance(User.meta.fields["name"], Field)
    assert User.meta.fields["name"].max_length == 100

    assert User(id=1) != Product(id=1)
    assert User(id=1) != User(id=2)
    assert User(id=1) == User(id=1)

    assert str(User(id=1)) == "User(id=1)"
    assert repr(User(id=1)) == "<User: User(id=1)>"

    assert isinstance(User.query.meta.fields["id"], Field)
    assert isinstance(User.query.meta.fields["name"], Field)


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


async def test_eq():
    user = await User.query.create(name="Test")
    assert user == user
    assert user != ""
    assert not user.__eq__("")
    assert user != User
    assert not user.__eq__(User)
