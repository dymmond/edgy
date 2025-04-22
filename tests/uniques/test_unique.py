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


class User(BaseModel):
    name = edgy.CharField(max_length=255, unique=True)
    email = edgy.CharField(max_length=60)


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    with models.database.force_rollback():
        async with models:
            yield


@pytest.mark.skipif(database.url.dialect == "mysql", reason="Not supported on MySQL")
async def test_unique():
    await User.query.create(name="Tiago", email="test@example.com")

    with pytest.raises(IntegrityError):
        await User.query.create(name="Tiago", email="test2@example.come")
