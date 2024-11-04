import pytest
from pydantic import ValidationError

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class MyModel(edgy.Model):
    name = edgy.fields.CharField(null=False, min_length=5, max_length=10)
    age = edgy.fields.IntegerField(null=False, ge=13)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_transactions():
    async with models:
        yield


async def test_pass_validator_fail_assignment():
    model = await MyModel.query.create(name="foobar", age=13)
    with pytest.raises(ValidationError):
        model.name = 7722
    with pytest.raises(ValidationError):
        model.name = "f"
    with pytest.raises(ValidationError):
        model.age = 1


async def test_create_fail_null():
    with pytest.raises(ValidationError):
        await MyModel.query.create()


async def test_create_fail_validator():
    with pytest.raises(ValidationError):
        await MyModel.query.create(name="foo", age=13)


async def test_create_fail_validator2():
    with pytest.raises(ValidationError):
        await MyModel.query.create(name="foobar", age=1)
