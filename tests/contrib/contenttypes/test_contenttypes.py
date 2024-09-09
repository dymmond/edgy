import pytest

import edgy
from edgy.contrib.contenttypes.fields import ContentTypeField
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, use_existing=False)
models = edgy.Registry(database=edgy.Database(database), with_content_type=True)


class ContentTypeTag(edgy.Model):
    ctype = edgy.fields.ForeignKey(to="ContentType", related_name="tags")
    tag = edgy.fields.CharField(max_length=50)

    content_type = edgy.fields.ExcludeField()

    class Meta:
        registry = models


class Organisation(edgy.Model):
    name = edgy.fields.CharField(max_length=100, unique=True)

    class Meta:
        registry = models


class Company(edgy.Model):
    name = edgy.fields.CharField(max_length=100, unique=True)

    class Meta:
        registry = models


class Person(edgy.Model):
    first_name = edgy.fields.CharField(max_length=100)
    last_name = edgy.fields.CharField(max_length=100)
    # to defaults to ContentType
    c = ContentTypeField()

    class Meta:
        registry = models
        unique_together = [("first_name", "last_name")]


class Profile(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    website = edgy.CharField(max_length=100)
    person = edgy.OneToOneField(
        Person,
        on_delete=edgy.CASCADE,
    )

    class Meta:
        registry = models


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


async def test_auto_created_contenttypes():
    model1 = await Company.query.create(name="edgy inc")
    model2 = await Organisation.query.create(name="edgy inc")
    assert model1.content_type.id is not None
    assert model1.content_type.name == "Company"
    assert model2.content_type.id is not None
    assert model2.content_type.name == "Organisation"
    tag = await model2.content_type.tags.add({"tag": "foo"})
    with pytest.raises(ValueError):
        tag.content_type  # noqa


async def test_collision():
    pass
