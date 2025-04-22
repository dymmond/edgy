import datetime
from enum import Enum

import pytest
from sqlalchemy.exc import IntegrityError

import edgy
from edgy.core.db.datastructures import UniqueConstraint
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


def time():
    return datetime.datetime.now().time()


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


class BaseModel(edgy.StrictModel):
    class Meta:
        registry = models


class AbsUser(edgy.StrictModel):
    name = edgy.CharField(max_length=255)
    email = edgy.CharField(max_length=60)

    class Meta:
        abstract = True
        unique_together = [UniqueConstraint(fields=["name", "email"])]


class User(AbsUser, BaseModel):
    name = edgy.CharField(max_length=255)
    email = edgy.CharField(max_length=60)


class AbsHubUser(edgy.StrictModel):
    name = edgy.CharField(max_length=255)
    email = edgy.CharField(max_length=60, null=True)
    age = edgy.IntegerField(gte=18, null=True)

    class Meta:
        abstract = True
        unique_together = [
            UniqueConstraint(fields=["name", "email"]),
            ("email", "age"),
        ]


class HubUser(AbsHubUser, BaseModel): ...


class AbsProduct(edgy.StrictModel):
    name = edgy.CharField(max_length=255)
    sku = edgy.CharField(max_length=255)

    class Meta:
        abstract = True
        unique_together = [UniqueConstraint(fields=["name"]), UniqueConstraint(fields=["sku"])]


class Product(AbsProduct, BaseModel): ...


class AbsNewProduct(edgy.StrictModel):
    name = edgy.CharField(max_length=255)
    sku = edgy.CharField(max_length=255)

    class Meta:
        abstract = True
        unique_together = [UniqueConstraint(fields=["name"]), "sku"]


class NewProduct(AbsNewProduct, BaseModel): ...


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    with models.database.force_rollback(True):
        async with models:
            yield


@pytest.mark.skipif(database.url.dialect == "mysql", reason="Not supported on MySQL")
async def test_unique_together():
    await User.query.create(name="Test", email="test@example.com")
    await User.query.create(name="Test", email="test2@example.come")

    with pytest.raises(IntegrityError):
        await User.query.create(name="Test", email="test@example.com")


@pytest.mark.skipif(database.url.dialect == "mysql", reason="Not supported on MySQL")
async def test_unique_together_multiple():
    await HubUser.query.create(name="Test", email="test@example.com")
    await HubUser.query.create(name="Test", email="test2@example.come")

    with pytest.raises(IntegrityError):
        await HubUser.query.create(name="Test", email="test@example.com")


@pytest.mark.skipif(database.url.dialect == "mysql", reason="Not supported on MySQL")
async def test_unique_together_multiple_name_age():
    await HubUser.query.create(name="NewTest", email="test@example.com", age=18)

    with pytest.raises(IntegrityError):
        await HubUser.query.create(name="Test", email="test@example.com", age=18)


@pytest.mark.skipif(database.url.dialect == "mysql", reason="Not supported on MySQL")
async def test_unique_together_multiple_single_string():
    await Product.query.create(name="android", sku="12345")

    with pytest.raises(IntegrityError):
        await Product.query.create(name="android", sku="12345")


@pytest.mark.skipif(database.url.dialect == "mysql", reason="Not supported on MySQL")
async def test_unique_together_multiple_single_string_two():
    await Product.query.create(name="android", sku="12345")

    with pytest.raises(IntegrityError):
        await Product.query.create(name="iphone", sku="12345")
