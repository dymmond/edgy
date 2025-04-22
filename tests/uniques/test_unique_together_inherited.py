import datetime
from enum import Enum

import pytest
from sqlalchemy.exc import IntegrityError

import edgy
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


class AbsUser(edgy.Model):
    name = edgy.CharField(max_length=255, index=True)
    email = edgy.CharField(max_length=60)

    class Meta:
        abstract = True
        unique_together = [("name", "email")]


class User(AbsUser, BaseModel): ...


class AbsHubUser(edgy.Model):
    name = edgy.CharField(max_length=255)
    title = edgy.CharField(max_length=255, null=True)
    description = edgy.CharField(max_length=255, null=True)

    class Meta:
        abstract = True
        unique_together = [("name", "email"), ("email", "age")]


class HubUser(AbsHubUser, BaseModel):
    name = edgy.CharField(max_length=255)
    email = edgy.CharField(max_length=60, null=True)
    age = edgy.IntegerField(gte=18, null=True)


class AbsProduct(edgy.Model):
    name = edgy.CharField(max_length=255)
    sku = edgy.CharField(max_length=255)

    class Meta:
        abstract = True
        unique_together = ["name", "sku"]


class Product(AbsProduct, BaseModel): ...


class AbsNewProduct(edgy.Model):
    name = edgy.CharField(max_length=255)
    sku = edgy.CharField(max_length=255)

    class Meta:
        abstract = True
        unique_together = ["name", "sku"]


class NewProduct(AbsNewProduct, BaseModel): ...


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
