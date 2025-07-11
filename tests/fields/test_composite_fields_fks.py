import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


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


class MyModel1(edgy.StrictModel):
    embedded: dict = edgy.CompositeField(
        inner_fields=[
            ("embedder", edgy.ForeignKey("MyModel1", null=True)),
        ],
    )

    class Meta:
        registry = models


class MyModelEmbed(edgy.StrictModel):
    embedder = edgy.ForeignKey("MyModel2", null=True)


class MyModel2(edgy.StrictModel):
    embedded = MyModelEmbed

    class Meta:
        registry = models


@pytest.mark.parametrize("model_class", [MyModel1, MyModel2])
async def test_model_create_update_delete(model_class):
    instance = await model_class.query.create()
    assert instance.id
    instance.embedded = {"embedder": instance}
    await instance.save()
    instance.model_dump()
    await instance.delete()
