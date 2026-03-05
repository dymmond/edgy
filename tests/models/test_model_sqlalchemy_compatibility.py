import uuid

import pytest
import sqlalchemy

import edgy
from edgy.exceptions import ImproperlyConfigured
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class Owner(edgy.SQLAlchemyModelMixin, edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class WorkspaceBase(edgy.SQLAlchemyModelMixin, edgy.StrictModel):
    code: str = edgy.CharField(max_length=100)

    class Meta:
        abstract = True
        registry = models


class Workspace(WorkspaceBase):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100)
    owner: Owner = edgy.ForeignKey(Owner, on_delete=edgy.CASCADE)

    class Meta:
        registry = models


class Tag(edgy.SQLAlchemyModelMixin, edgy.StrictModel):
    id: uuid.UUID = edgy.UUIDField(primary_key=True, default=uuid.uuid4)
    label: str = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Article(edgy.SQLAlchemyModelMixin, edgy.StrictModel):
    id: str = edgy.CharField(max_length=30, primary_key=True)
    tags: list[Tag] = edgy.ManyToMany(Tag, through_tablename=edgy.NEW_M2M_NAMING)

    class Meta:
        registry = models


class PlainWorkspace(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100)

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
    async with models:
        yield


async def test_sqlalchemy_core_class_attribute_select_where_and_order_by():
    owner = await Owner.query.create(name="ACME")
    workspace1 = await Workspace.query.create(name="Alpha", code="alpha", owner=owner)
    workspace2 = await Workspace.query.create(name="Beta", code="beta", owner=owner)

    statement = sqlalchemy.select(Workspace.id).where(Workspace.id == workspace1.id)
    row = await models.database.fetch_one(statement)
    assert row is not None
    assert row[0] == workspace1.id

    order_statement = sqlalchemy.select(Workspace.id).order_by(Workspace.id)
    ordered_rows = await models.database.fetch_all(order_statement)
    assert [row[0] for row in ordered_rows] == [workspace1.id, workspace2.id]

    assert workspace1 == await Workspace.query.filter(Workspace.id == workspace1.id).get()


async def test_opted_out_models_keep_old_behavior():
    with pytest.raises(AttributeError):
        _ = PlainWorkspace.id


async def test_foreign_key_alias_is_supported_but_relationship_name_is_rejected():
    owner = await Owner.query.create(name="Owner")
    workspace = await Workspace.query.create(name="Workspace", code="workspace", owner=owner)

    with pytest.raises(ImproperlyConfigured, match='Field "owner"'):
        _ = Workspace.owner

    statement = sqlalchemy.select(Workspace.owner_id).where(Workspace.owner_id == owner.id)
    row = await models.database.fetch_one(statement)
    assert row is not None
    assert row[0] == owner.id

    join_statement = (
        sqlalchemy.select(Workspace.id)
        .select_from(Workspace.table.join(Owner.table, Workspace.owner_id == Owner.id))
        .where(Owner.id == owner.id)
    )
    joined_row = await models.database.fetch_one(join_statement)
    assert joined_row is not None
    assert joined_row[0] == workspace.id


async def test_inherited_field_columns_are_available():
    owner = await Owner.query.create(name="Inherited")
    workspace = await Workspace.query.create(name="Child", code="inherit", owner=owner)

    statement = sqlalchemy.select(Workspace.code).where(Workspace.code == "inherit")
    row = await models.database.fetch_one(statement)
    assert row is not None
    assert row[0] == workspace.code


async def test_compatibility_can_be_declared_once_on_abstract_base():
    with pytest.raises(AttributeError):
        _ = WorkspaceBase.code

    owner = await Owner.query.create(name="AbstractOwner")
    workspace = await Workspace.query.create(name="AbstractChild", code="base-code", owner=owner)

    statement = sqlalchemy.select(Workspace.code).where(Workspace.code == "base-code")
    row = await models.database.fetch_one(statement)
    assert row is not None
    assert row[0] == workspace.code


async def test_relationship_collections_are_not_scalar_columns():
    with pytest.raises(ImproperlyConfigured, match="many-to-many relation"):
        _ = Article.tags


async def test_primary_key_variants_uuid_and_string():
    tag = await Tag.query.create(label="backend")
    article = await Article.query.create(id="article-1")

    tag_row = await models.database.fetch_one(sqlalchemy.select(Tag.id).where(Tag.id == tag.id))
    assert tag_row is not None
    assert tag_row[0] == tag.id

    article_row = await models.database.fetch_one(
        sqlalchemy.select(Article.id).where(Article.id == article.id)
    )
    assert article_row is not None
    assert article_row[0] == article.id
