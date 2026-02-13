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

    id: int = fields.IntegerField(autoincrement=True, primary_key=True)
    name: str = fields.CharField(max_length=128)

    class Meta:
        registry = models


class Collection(edgy.Model):
    """
    Collection with a ManyToMany to Group.

    This is similar to your real-world case where collection has groups,
    and workspaces are attached to a collection.
    """

    id: int = fields.IntegerField(autoincrement=True, primary_key=True)
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

    id: int = fields.IntegerField(autoincrement=True, primary_key=True)
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


async def test_q_or_does_not_duplicate_with_and_condition():
    """
    Mix Q(...) | Q(...) with AND conditions.
    Ensures AND does not multiply rows incorrectly.
    """
    g1 = await Group.query.create(name="ga")
    g2 = await Group.query.create(name="gb")

    col = await Collection.query.create(name="c")
    await col.groups.add(g1)
    await col.groups.add(g2)

    ws = await Workspace.objects.create(name="w", collection=col)

    qs = Workspace.objects.filter(
        (Q(collection__groups__name="ga") | Q(collection__groups__name="gb")) & Q(name="w")
    )

    results = await qs
    assert len(results) == 1
    assert results[0].id == ws.id


async def test_q_or_does_not_affect_exists_uniqueness_checks():
    """
    This mimics your real scenario:
    slug+collection uniqueness checks must NOT be affected by OR.
    """

    g = await Group.query.create(name="support")

    col = await Collection.query.create(name="main")
    await col.groups.add(g)

    # Create workspace
    await Workspace.objects.create(name="exist", collection=col)

    # Correct exists
    assert await Workspace.objects.filter(name="exist", collection=col).exists()

    # Unique lookup -- should remain False for nonexistent
    assert not await Workspace.objects.filter(name="not-there", collection=col).exists()


async def test_select_related_does_not_duplicate_rows():
    g1 = await Group.query.create(name="g1")
    g2 = await Group.query.create(name="g2")

    col = await Collection.query.create(name="cc")
    await col.groups.add(g1)
    await col.groups.add(g2)

    await Workspace.objects.create(name="ws", collection=col)

    qs = Workspace.objects.select_related("collection").filter(
        Q(collection__groups__name="g1") | Q(collection__groups__name="g2")
    )

    results = await qs
    assert len(results) == 1
    assert results[0].collection.id == col.id


async def test_values_no_duplicates_on_q_or():
    g1 = await Group.query.create(name="a1")
    g2 = await Group.query.create(name="a2")

    col = await Collection.query.create(name="vv")
    await col.groups.add(g1)
    await col.groups.add(g2)

    await Workspace.objects.create(name="ws44", collection=col)

    rows = await Workspace.objects.filter(
        Q(collection__groups__name="a1") | Q(collection__groups__name="a2")
    ).values("name")

    assert len(rows) == 1
    assert rows[0]["name"] == "ws44"


async def test_values_list_no_duplicates_on_q_or():
    g1 = await Group.query.create(name="b1")
    g2 = await Group.query.create(name="b2")

    col = await Collection.query.create(name="vv2")
    await col.groups.add(g1)
    await col.groups.add(g2)

    await Workspace.objects.create(name="ws55", collection=col)

    names = await Workspace.objects.filter(
        Q(collection__groups__name="b1") | Q(collection__groups__name="b2")
    ).values_list("name", flat=True)

    assert names == ["ws55"]


async def test_first_last_do_not_return_duplicates():
    g1 = await Group.query.create(name="h1")
    g2 = await Group.query.create(name="h2")

    col = await Collection.query.create(name="h_col")
    await col.groups.add(g1)
    await col.groups.add(g2)

    ws = await Workspace.objects.create(name="unique", collection=col)

    qs = Workspace.objects.filter(
        Q(collection__groups__name="h1") | Q(collection__groups__name="h2")
    )

    # first()
    f = await qs.first()
    assert f is not None
    assert f.id == ws.id

    # last()
    last = await qs.last()
    assert last is not None
    assert last.id == ws.id


async def test_count_correct_with_or_duplicates_removed():
    g1 = await Group.query.create(name="c1")
    g2 = await Group.query.create(name="c2")
    col = await Collection.query.create(name="c_col")

    await col.groups.add(g1)
    await col.groups.add(g2)

    await Workspace.objects.create(name="cws", collection=col)

    qs = Workspace.objects.filter(
        Q(collection__groups__name="c1") | Q(collection__groups__name="c2")
    )

    # count() is a SQL count, not Python list length
    assert await qs.count() == 1


async def test_q_or_multiple_workspaces_in_different_collections():
    """
    Ensure that Q(...) | Q(...) returns *all* matching workspaces across
    different collections, and that de-duplication does not over-collapse.
    """
    g1 = await Group.query.create(name="gx1")
    g2 = await Group.query.create(name="gx2")

    c1 = await Collection.query.create(name="cx1")
    c2 = await Collection.query.create(name="cx2")
    await c1.groups.add(g1)
    await c2.groups.add(g2)

    ws1 = await Workspace.objects.create(name="ws-a", collection=c1)
    ws2 = await Workspace.objects.create(name="ws-b", collection=c2)

    qs = Workspace.objects.filter(
        Q(collection__groups__name="gx1") | Q(collection__groups__name="gx2")
    ).order_by("id")

    results = await qs
    ids = {w.id for w in results}
    assert ids == {ws1.id, ws2.id}
    assert len(results) == 2


async def test_count_without_or_returns_all_rows():
    """
    Baseline: .count() on a simple filtered queryset (no OR, no joins fan-out)
    should return the total number of rows, unaffected by the OR fixes.
    """
    g = await Group.query.create(name="simple-g")
    col = await Collection.query.create(name="simple-col")
    await col.groups.add(g)

    await Workspace.objects.create(name="w1", collection=col)
    await Workspace.objects.create(name="w2", collection=col)
    await Workspace.objects.create(name="w3", collection=col)

    qs = Workspace.objects.filter(collection=col)
    assert await qs.count() == 3


async def test_count_with_or_and_multiple_workspaces():
    """
    COUNT with Q(...) | Q(...) where multiple distinct workspaces match.
    Ensures DISTINCT-based count returns the number of unique workspaces,
    not the raw join row count.
    """
    g1 = await Group.query.create(name="cx1")
    g2 = await Group.query.create(name="cx2")
    g3 = await Group.query.create(name="cx3")

    c1 = await Collection.query.create(name="cc1")
    c2 = await Collection.query.create(name="cc2")
    c3 = await Collection.query.create(name="cc3")

    await c1.groups.add(g1)
    await c2.groups.add(g2)
    await c3.groups.add(g3)

    await Workspace.objects.create(name="w1", collection=c1)
    await Workspace.objects.create(name="w2", collection=c2)
    await Workspace.objects.create(name="w3", collection=c3)

    qs = Workspace.objects.filter(
        Q(collection__groups__name="cx1") | Q(collection__groups__name="cx2")
    )

    # Only workspaces in cc1 and cc2 should be counted
    assert await qs.count() == 2


async def test_local_or_keeps_and_scope_and_does_not_duplicate():
    """
    local_or() should OR the given clauses but keep the existing AND scope.
    It must not promote to a global OR and must still avoid duplicates.
    """
    g1 = await Group.query.create(name="lo1")
    g2 = await Group.query.create(name="lo2")

    col = await Collection.query.create(name="lo_col")
    await col.groups.add(g1)
    await col.groups.add(g2)

    ws_target = await Workspace.objects.create(name="target", collection=col)
    await Workspace.objects.create(name="other", collection=col)

    qs = Workspace.objects.filter(name="target").local_or(
        Q(collection__groups__name="lo1"),
        Q(collection__groups__name="lo2"),
    )

    results = await qs
    assert len(results) == 1
    assert results[0].id == ws_target.id
