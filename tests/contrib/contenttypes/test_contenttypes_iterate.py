import asyncio

import pytest

import edgy
from edgy.contrib.contenttypes.fields import ContentTypeField
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, force_rollback=False, full_isolation=False)
models = edgy.Registry(database=database, with_content_type=True)


class ContentTypeTag(edgy.StrictModel):
    ctype = edgy.fields.ForeignKey(to="ContentType", related_name="tags")
    tag = edgy.fields.CharField(max_length=50)

    content_type = edgy.fields.ExcludeField()

    class Meta:
        registry = models


class Organisation(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100, unique=True)

    class Meta:
        registry = models


class Company(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100, unique=True)

    class Meta:
        registry = models


class Person(edgy.StrictModel):
    first_name = edgy.fields.CharField(max_length=100)
    last_name = edgy.fields.CharField(max_length=100)
    # to defaults to registry.content_type
    c = ContentTypeField()

    class Meta:
        registry = models
        unique_together = [("first_name", "last_name")]


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


async def test_iterate():
    model1 = await Company.query.create(name="edgy inc")
    model2 = await Organisation.query.create(name="edgy inc")
    assert model1.content_type.id is not None
    assert model1.content_type.name == "Company"
    assert model2.content_type.id is not None
    assert model2.content_type.name == "Organisation"
    tag = await model2.content_type.tags.add({"tag": "foo"})
    with pytest.raises(ValueError):
        tag.content_type  # noqa
    model_after_load = await Company.query.get(id=model1.id)
    assert model_after_load.content_type.id is not None
    # defer
    assert model_after_load.content_type.name == "Company"
    assert await model_after_load.content_type.get_instance() == model1
    # count
    assert await models.content_type.query.count() == 2
    # iterate
    # we need create_task otherwise the connection is reused
    [
        await asyncio.create_task(content_type.get_instance())
        async for content_type in models.content_type.query.all()
    ]

    # we cannot iterate without deadlocking because of force_rollback
