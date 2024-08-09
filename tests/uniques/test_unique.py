import datetime
from enum import Enum

import pytest
from sqlalchemy.exc import IntegrityError

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, test_prefix="")
models = edgy.Registry(database=database)


def time():
    return datetime.datetime.now().time()


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


class BaseModel(edgy.Model):
    class Meta:
        registry = models


class User(BaseModel):
    name = edgy.CharField(max_length=255, unique=True)
    email = edgy.CharField(max_length=60)


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_transactions():
    with database.force_rollback():
        async with database:
            yield


@pytest.mark.skipif(database.url.dialect == "mysql", reason="Not supported on MySQL")
async def test_unique():
    await User.query.create(name="Tiago", email="test@example.com")

    with pytest.raises(IntegrityError):
        await User.query.create(name="Tiago", email="test2@example.come")
