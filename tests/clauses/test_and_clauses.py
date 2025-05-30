import pytest

import edgy
from edgy.core.db.querysets.clauses import Q, and_
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)
    email = edgy.EmailField(null=True, max_length=255)

    class Meta:
        registry = models


class Product(edgy.StrictModel):
    user = edgy.ForeignKey(User, related_name="products")

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    # this creates and drops the database
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    # this rolls back
    async with models:
        yield


async def test_filter_with_empty_and():
    await User.query.create(name="Adam", language="EN")

    results = await User.query.filter(and_())

    assert len(results) == 1


async def test_filter_with_empty_Q():
    await User.query.create(name="Adam", language="EN")

    results = await User.query.filter(Q())

    assert len(results) == 1


async def test_filter_with_and():
    user = await User.query.create(name="Adam", language="EN")

    results = await User.query.filter(and_(User.columns.name == "Adam"))

    assert len(results) == 1
    assert results[0].pk == user.pk


async def test_filter_with_and_two():
    await User.query.create(name="Adam")
    await User.query.create(name="Edgy")

    results = await User.query.filter(
        and_(User.columns.name == "Adam", User.columns.name == "Edgy")
    )

    assert len(results) == 0


async def test_filter_with_and_two_kwargs_with_user():
    user = await User.query.create(name="Adam", email="edgy@edgy.dev")
    await User.query.create(name="Edgy", email="edgy2@edgy.dev")

    with pytest.warns(DeprecationWarning):
        results = await User.query.filter(
            and_.from_kwargs(User, name="Adam", email="edgy@edgy.dev")
        )

    assert len(results) == 1
    assert results[0].pk == user.pk

    with pytest.warns(DeprecationWarning):
        results = await User.query.filter(
            and_.from_kwargs(User, name="Adam", email="edgy@edgy.dev")
        )

    assert len(results) == 1
    assert results[0].pk == user.pk


async def test_filter_with_and_two_kwargs_no_user():
    user = await User.query.create(name="Adam", email="edgy@edgy.dev")
    await User.query.create(name="Edgy", email="edgy2@edgy.dev")

    results = await User.query.filter(and_.from_kwargs(name="Adam", email="edgy@edgy.dev"))

    assert len(results) == 1
    assert results[0].pk == user.pk

    results = await User.query.filter(and_.from_kwargs(name="Adam", email="edgy@edgy.dev"))

    assert len(results) == 1
    assert results[0].pk == user.pk


async def test_filter_with_and_three():
    await User.query.create(name="Adam")
    user = await User.query.create(name="Edgy", email="edgy@edgy.dev")

    results = await User.query.filter(
        and_(User.columns.name == user.name, User.columns.email == user.email)
    )

    assert len(results) == 1


async def test_filter_with_and_four():
    await User.query.create(name="Adam")
    user = await User.query.create(name="Edgy", email="edgy@edgy.dev")

    results = await User.query.filter(and_(User.columns.name == user.name)).filter(
        and_(User.columns.email == user.email)
    )
    assert len(results) == 1


async def test_filter_with_contains():
    await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Edgy", email="edgy@edgy.dev")

    results = await User.query.filter(and_(User.columns.email.contains("edgy")))
    assert len(results) == 2


async def test_filter_and_clause_style():
    user = await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Edgy", email="edgy@edgy.dev")

    results = await User.query.and_(name="Adam", email__icontains="edgy")

    assert len(results) == 1
    assert results[0].pk == user.pk

    results = await User.query.and_(email__icontains="edgy")

    assert len(results) == 2


async def test_filter_and_clause_style_nested():
    user = await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Edgy", email="edgy@edgy.dev")

    results = await User.query.and_(name="Adam").and_(email__icontains="edgy")

    assert len(results) == 1
    assert results[0].pk == user.pk


async def test_filter_and_clause_related():
    user = await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Edgy", email="edgy@edgy.dev")
    product = await Product.query.create(user=user)

    results = await Product.query.and_(user__id=user.pk)

    assert len(results) == 1
    assert results[0].pk == product.pk

    results = await User.query.and_(products__id=product.pk)

    assert len(results) == 1
    assert results[0].pk == user.pk


async def test_filter_and_clause_related_helper():
    user = await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Edgy", email="edgy@edgy.dev")
    product = await Product.query.create(user=user)

    results = await Product.query.filter(and_.from_kwargs(user__id=user.pk))

    assert len(results) == 1
    assert results[0].pk == product.pk

    results = await User.query.filter(and_.from_kwargs(products__id=product.pk))

    assert len(results) == 1
    assert results[0].pk == user.pk
