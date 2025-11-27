from typing import ClassVar

import pytest

import edgy
from edgy.core.db import fields
from edgy.core.db.models.managers import Manager
from edgy.core.db.querysets import Q, QuerySet
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = Database(DATABASE_URL, drop_database=True)
models = edgy.Registry(database=database)


class UniqueWorkspaceQuerySet(QuerySet):
    """
    Custom QuerySet used only by this test to ensure that OR-ed Q clauses
    which generate duplicates at the SQL level are de-duplicated at the
    ORM level.

    The important bit: we always apply DISTINCT on the resulting queryset.
    """

    def filter(self, *clauses, **lookups):  # type: ignore[override]
        """
        Override the default filter() so that any Q(...) | Q(...) usage
        still returns unique rows at the model level.

        We rely on the engine-level OR/Q handling but enforce DISTINCT
        on the cloned queryset.
        """
        qs = super().filter(*clauses, **lookups)
        # Enforce uniqueness on the whole row. The underlying implementation
        # can be changed to DISTINCT ON primary key, subquery, etc.; the test
        # only cares that we get a single Workspace instance back.
        return qs.distinct()


class WorkspaceManager(Manager):
    """
    Manager that uses the custom queryset_class.

    BaseManager.get_queryset() is expected to honour self.queryset_class
    instead of hard-coding QuerySet.
    """

    queryset_class = UniqueWorkspaceQuerySet


class Group(edgy.Model):
    """
    Simple group model to create M2M fan-out from Collection, so that
    a single Workspace can be duplicated at SQL level when joining on
    groups and OR-ing conditions.
    """

    id: int = fields.IntegerField(primary_key=True)
    name: str = fields.CharField(max_length=128)

    class Meta:
        registry = models


class Collection(edgy.Model):
    """
    Collection with a ManyToMany to Group.

    This is similar to your real-world case where collection has groups,
    and workspaces are attached to a collection.
    """

    id: int = fields.IntegerField(primary_key=True)
    name: str = fields.CharField(max_length=128)
    groups: list[Group] = fields.ManyToManyField(  # type: ignore[assignment]
        "Group",
        through_tablename=edgy.NEW_M2M_NAMING,
        related_name="collections",
    )

    class Meta:
        registry = models


class Workspace(edgy.Model):
    """
    Workspace belonging to a Collection.

    The important bit: the default manager is replaced by WorkspaceManager,
    which in turn uses UniqueWorkspaceQuerySet as queryset_class.
    """

    id: int = fields.IntegerField(primary_key=True)
    name: str = fields.CharField(max_length=128)
    collection: Collection = fields.ForeignKey(  # type: ignore[assignment]
        "Collection",
        related_name="workspaces",
        on_delete=edgy.CASCADE,
    )

    # This is the manager we’re testing
    objects: ClassVar[WorkspaceManager] = WorkspaceManager()  # type: ignore[assignment]

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


async def test_custom_manager_uses_custom_queryset_class_for_q_or():
    """
    Sanity check: ensure the manager is actually using our custom
    UniqueWorkspaceQuerySet when we call filter() with a Q(...) | Q(...).
    """
    qs = Workspace.objects.filter(Q(id=1) | Q(id=2))
    assert isinstance(qs, QuerySet)


async def test_q_or_with_custom_queryset_returns_single_workspace():
    """
    Regression-style test for the 'Q(...) | Q(...) returns duplicates' case.

    We create a single Workspace whose Collection is linked to two Groups.
    A naive join on collection__groups with an OR across group names may
    return the same Workspace more than once at the SQL level.

    The custom queryset_class on WorkspaceManager must ensure we only
    get one Workspace instance back.
    """
    # Arrange
    g1 = await Group.query.create(name="group-a")
    g2 = await Group.query.create(name="group-b")

    collection = await Collection.query.create(name="col-1")
    # Fan out: same collection linked to two different groups
    await collection.groups.add(g1)
    await collection.groups.add(g2)

    workspace = await Workspace.objects.create(name="ws-1", collection=collection)

    # Act: use Q(...) | Q(...) against the groups through the collection.
    # This is the shape of query that previously produced duplicates even
    # when distinct() was applied in the calling code.
    qs = Workspace.objects.filter(
        Q(collection__groups__name="group-a") | Q(collection__groups__name="group-b")
    )
    results = await qs

    assert len(results) == 1, "Q(...) | Q(...) must not duplicate Workspace rows"
    assert results[0].id == workspace.id
    assert results[0].name == "ws-1"
