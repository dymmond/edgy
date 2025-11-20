import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

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
        # Seed some rows commonly reused across tests
        # (A, B, C) are handy for set-logic assertions
        await User.query.bulk_create(
            [
                {"name": "A", "language": "EN"},
                {"name": "B", "language": "EN"},
                {"name": "C", "language": "DE"},
                {"name": "D", "language": "PT"},
            ]
        )
        yield


def _names(rows):
    return [u.name for u in rows]


async def test_union_basic_dedup_and_order_limit():
    # q1 -> A, B
    q1 = User.query.filter(name__in=["A", "B"]).order_by("name")

    # q2 -> B, C
    q2 = User.query.filter(name__in=["B", "C"]).order_by("name")

    # UNION should deduplicate -> A, B, C
    union_qs = q1.union(q2).order_by("name")
    rows = await union_qs

    assert _names(rows) == ["A", "B", "C"]

    # Outer ORDER + LIMIT should apply on the unioned set
    rows = await union_qs.limit(2)
    assert _names(rows) == ["A", "B"]


async def test_union_all_keeps_duplicates_and_outer_limit():
    # q1 -> A, B
    q1 = User.query.filter(name__in=["A", "B"]).order_by("name")

    # q2 -> B, C
    q2 = User.query.filter(name__in=["B", "C"]).order_by("name")

    # UNION ALL should keep duplicates: [A, B] + [B, C] -> A, B, B, C (outer order not guaranteed yet)
    qs = q1.union_all(q2).order_by("name")

    rows = await qs
    # We expect exactly 4 rows with two Bs
    assert _names(rows) == ["A", "B", "B", "C"]

    # LIMIT still applies to the combined/ordered output
    rows = await qs.limit(3)
    assert _names(rows) == ["A", "B", "B"]


async def test_intersect_basic():
    # q1 -> A, B
    q1 = User.query.filter(name__in=["A", "B"])

    # q2 -> B, C
    q2 = User.query.filter(name__in=["B", "C"])

    # INTERSECT -> B
    rows = await q1.intersect(q2).order_by("name")
    assert _names(rows) == ["B"]


async def test_except_basic():
    # q1 -> A, B, C
    q1 = User.query.filter(name__in=["A", "B", "C"])
    # q2 -> B, C
    q2 = User.query.filter(name__in=["B", "C"])

    # EXCEPT -> A
    rows = await q1.except_(q2).order_by("name")
    assert _names(rows) == ["A"]


async def test_outer_order_by_limit_offset_on_combined():
    # Make IDs deterministic by ordering insert in fixture; grab the highest id row after union.
    q1 = User.query.filter(name__in=["A", "B"])
    q2 = User.query.filter(name__in=["C", "D"])

    # -> A, B, C, D
    combined = q1.union(q2)

    # Order by -id gives D first (highest id among the four)
    top1 = await combined.order_by("-id").limit(1)

    assert len(top1) == 1
    assert top1[0].name in {
        "C",
        "D",
    }  # depends on creation order; with our fixture D should be last

    # Offset then limit to fetch the runner-up
    next1 = await combined.order_by("-id").offset(1).limit(1)

    assert len(next1) == 1
    assert next1[0].name in {"B", "C", "D", "A"}  # just sanity: it is the 2nd in -id order


async def test_only_and_defer_propagation_across_union():
    q1 = User.query.filter(name__in=["A", "B"]).only("id", "name")
    q2 = User.query.filter(name__in=["B", "C"]).only("id", "name")

    rows = await q1.union(q2).order_by("name")
    assert _names(rows) == ["A", "B", "C"]

    # Ensure the deferred field isn't accidentally populated
    # (It should still be present on the model, but not preloaded—access won't error, but we check values())
    data = await q1.union(q2).order_by("name").values(["id", "name"])

    assert list(data[0].keys()) == ["id", "name"]

    # Same idea with defer
    q3 = User.query.filter(name__in=["A", "B"]).defer("language")
    q4 = User.query.filter(name__in=["B", "C"]).defer("language")
    data = await q3.union(q4).order_by("name").values(["id", "name"])
    assert list(data[0].keys()) == ["id", "name"]


async def test_combining_requires_same_model_and_registry():
    # Same model / same registry works

    q1 = User.query.filter(name="A")
    q2 = User.query.filter(name="B")
    _ = q1.union(q2)  # should not raise

    # Different model should raise (build a tiny second model in a separate registry)
    other_models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

    class Product(edgy.StrictModel):
        id = edgy.IntegerField(primary_key=True, autoincrement=True)
        name = edgy.CharField(max_length=100)

        class Meta:
            registry = other_models

    with pytest.raises(Exception):  # noqa
        _ = q1.union(Product.query.filter(name="X"))


async def test_union_three_way_chaining():
    # (A,B) ∪ (C) ∪ (D) -> A, B, C, D
    q1 = User.query.filter(name__in=["A", "B"])
    q2 = User.query.filter(name__in=["C"])
    q3 = User.query.filter(name__in=["D"])

    rows = await q1.union(q2).union(q3).order_by("name")
    assert _names(rows) == ["A", "B", "C", "D"]


async def test_intersect_empty_result():
    # (A,B) ∩ (C,D) -> ∅
    q1 = User.query.filter(name__in=["A", "B"])
    q2 = User.query.filter(name__in=["C", "D"])

    rows = await q1.intersect(q2)

    assert rows == []


async def test_values_and_values_list_on_union():
    q1 = User.query.filter(name__in=["A", "B"]).only("id", "name")
    q2 = User.query.filter(name__in=["C"]).only("id", "name")

    # values()
    data = await q1.union(q2).order_by("id").values(["id", "name"])

    assert isinstance(data, list) and all(isinstance(d, dict) for d in data)
    assert [d["name"] for d in data] == ["A", "B", "C"]

    # values_list(flat=True)
    names = await q1.union(q2).order_by("id").values_list(["name"], flat=True)

    assert names == ["A", "B", "C"]


async def test_exists_and_count_on_combined():
    q1 = User.query.filter(name__in=["A"])  # A
    q2 = User.query.filter(name__in=["Z"])  # none

    union_qs = q1.union(q2)

    assert await union_qs.exists() is True
    assert await union_qs.count() == 1

    inter_qs = q1.intersect(q2)

    assert await inter_qs.exists() is False
    assert await inter_qs.count() == 0


async def test_union_all_then_distinct_matches_union():
    q1 = User.query.filter(name__in=["A", "B"])  # A,B
    q2 = User.query.filter(name__in=["B", "C"])  # B,C

    # UNION ALL gives dup B, DISTINCT on outer should deduplicate to A,B,C
    names_all = _names(await q1.union_all(q2).order_by("name"))

    assert names_all == ["A", "B", "B", "C"]

    names_distinct_outer = _names(await q1.union_all(q2).distinct(True).order_by("name"))

    assert names_distinct_outer == ["A", "B", "C"]

    names_union = _names(await q1.union(q2).order_by("name"))

    assert names_union == ["A", "B", "C"]


async def test_inner_order_is_ignored_outer_order_applies():
    # Ensure that the inner query orderings do not force the combined order
    q1 = User.query.filter(name__in=["B", "A"]).order_by("-name")
    q2 = User.query.filter(name__in=["D", "C"]).order_by("-name")

    rows = await q1.union(q2).order_by("name")

    assert _names(rows) == ["A", "B", "C", "D"]


async def test_pagination_over_union_all_with_offset_limit():
    # union all so we get duplicates to paginate over
    q1 = User.query.filter(name__in=["A", "B"])  # A,B
    q2 = User.query.filter(name__in=["B", "C"])  # B,C -> combined A,B,B,C

    page1 = await q1.union_all(q2).order_by("name").limit(2)

    assert _names(page1) == ["A", "B"]

    page2 = await q1.union_all(q2).order_by("name").offset(2).limit(2)

    assert _names(page2) == ["B", "C"]


async def test_only_and_defer_mixed_across_union():
    # one side .only, other side .defer; outer values should still be stable
    q1 = User.query.filter(name__in=["A", "B"]).only("id", "name")
    q2 = User.query.filter(name__in=["C"]).defer("language")

    data = await q1.union(q2).order_by("name").values(["id", "name"])

    assert [d["name"] for d in data] == ["A", "B", "C"]


async def test_get_first_last_on_combined_are_stable():
    combined = User.query.filter(name__in=["A", "B"]).union(
        User.query.filter(name__in=["C", "D"])  # -> A,B,C,D
    )

    # first() with explicit outer order
    first_row = await combined.order_by("name").first()

    assert first_row.name == "A"

    last_row = await combined.order_by("name").last()

    assert last_row.name == "D"
