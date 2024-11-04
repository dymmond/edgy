import asyncio

import pytest
from sqlalchemy.exc import IntegrityError

import edgy
from edgy.contrib.contenttypes.fields import ContentTypeField
from edgy.contrib.contenttypes.models import ContentType as _ContentType
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL


class ExplicitContentType(_ContentType):
    custom_field = edgy.CharField(max_length=1, null=True)
    custom_field_non_inherited = edgy.CharField(max_length=1, null=True, inherit=False)

    class Meta:
        abstract = True


pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, use_existing=False)
models = edgy.Registry(
    database=edgy.Database(database, force_rollback=True), with_content_type=ExplicitContentType
)


class ContentTypeTag(edgy.StrictModel):
    ctype = edgy.fields.ForeignKey(to="ContentType", related_name="tags", on_delete=edgy.CASCADE)
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
    # to defaults to ContentType
    c = ContentTypeField()

    class Meta:
        registry = models
        unique_together = [("first_name", "last_name")]


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    async with models.database:
        yield


async def test_registry_sanity():
    assert models.content_type is models.get_model("ContentType")
    assert "custom_field" in models.content_type.meta.fields


async def test_default_contenttypes():
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
    # fetch_all
    [await content_type.get_instance() for content_type in await models.content_type.query.all()]
    # iterate
    with pytest.warns(UserWarning):
        ops = [
            content_type.get_instance() async for content_type in models.content_type.query.all()
        ]
    await asyncio.gather(*ops)
    await models.content_type.query.delete()
    assert await Company.query.get_or_none(name="edgy inc") is None


async def test_explicit_contenttypes():
    # no name but still should work
    model1 = await Company.query.create(name="edgy inc", content_type={})
    # wrong name type, but should be autocorrected
    model2 = await Organisation.query.create(name="edgy inc", content_type={"name": "Company"})
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
    await models.content_type.query.delete()
    assert await Company.query.get_or_none(name="edgy inc") is None


async def test_collision():
    assert await Company.query.count() == 0
    model1 = await Company.query.create(
        name="edgy inc", content_type={"collision_key": "edgy inc"}
    )
    assert model1.content_type.collision_key == "edgy inc"
    with pytest.raises(IntegrityError):
        await Organisation.query.create(
            name="edgy inc", content_type={"collision_key": "edgy inc"}
        )
    assert await Organisation.query.count() == 0
