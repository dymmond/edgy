import pytest

import edgy
from edgy.core.db.querysets.clauses import or_
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)
    email = edgy.EmailField(null=True, max_length=255)

    class Meta:
        registry = models


class Product(edgy.Model):
    user = edgy.ForeignKey(User, related_name="products")

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


async def test_filter_with_empty_or():
    await User.query.create(name="Adam", language="EN")

    results = await User.query.filter(or_())

    assert len(results) == 0


async def test_filter_with_or():
    user = await User.query.create(name="Adam")

    results = await User.query.filter(
        or_(User.columns.name == "Adam", User.columns.name == "Edgy")
    )

    assert len(results) == 1
    assert results[0].pk == user.pk


async def test_filter_with_or_two():
    await User.query.create(name="Adam")
    await User.query.create(name="Edgy")

    results = await User.query.filter(
        or_(User.columns.name == "Adam", User.columns.name == "Edgy")
    )

    assert len(results) == 2


async def test_filter_with_or_two_kwargs_with_user():
    await User.query.create(name="Adam", email="edgy@edgy.dev")
    await User.query.create(name="Edgy", email="edgy2@edgy.dev")

    with pytest.warns(DeprecationWarning):
        results = await User.query.filter(
            or_.from_kwargs(User.columns, name="Adam", email="edgy2@edgy.dev")
        )

    assert len(results) == 2

    with pytest.warns(DeprecationWarning):
        results = await User.query.filter(
            or_.from_kwargs(User, name="Adam", email="edgy2@edgy.dev")
        )

    assert len(results) == 2


async def test_filter_with_or_two_kwargs_no_user():
    await User.query.create(name="Adam", email="edgy@edgy.dev")
    await User.query.create(name="Edgy", email="edgy2@edgy.dev")

    results = await User.query.filter(or_.from_kwargs(name="Adam", email="edgy2@edgy.dev"))

    assert len(results) == 2

    results = await User.query.filter(or_.from_kwargs(name="Adam", email="edgy2@edgy.dev"))

    assert len(results) == 2


async def test_filter_with_or_three():
    await User.query.create(name="Adam")
    user = await User.query.create(name="Edgy", email="edgy@edgy.dev")

    results = await User.query.filter(
        or_(User.columns.name == "Adam", User.columns.email == user.email)
    )

    assert len(results) == 2


async def test_filter_with_or_four():
    await User.query.create(name="Adam")
    user = await User.query.create(name="Edgy", email="edgy@edgy.dev")

    results = await User.query.filter(or_(User.columns.name == user.name)).filter(
        or_(User.columns.email == user.email)
    )
    assert len(results) == 1


async def test_filter_with_contains():
    await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Edgy", email="edgy@edgy.dev")

    results = await User.query.filter(or_(User.columns.email.contains("edgy")))
    assert len(results) == 2


async def test_filter_or_clause_style_nested():
    user = await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Edgy", email="edgy@edgy.dev")

    results = await User.query.or_(name="Adam").or_(email__icontains=user.email)

    assert len(results) == 1
    assert results[0].pk == user.pk

    results = await User.query.or_(email__icontains="edgy")

    assert len(results) == 2


async def test_filter_or_clause_related():
    user = await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Edgy", email="edgy@edgy.dev")
    product = await Product.query.create(user=user)

    results = await Product.query.or_(user__id=user.pk)

    assert len(results) == 1
    assert results[0].pk == product.pk

    results = await User.query.or_(products__id=product.pk)

    assert len(results) == 1
    assert results[0].pk == user.pk


async def test_filter_or_clause_select():
    user = await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Edgy", email="adam@edgy.dev")

    results = await User.query.or_(name="Test").or_(name="Adam")

    assert len(results) == 1
    assert results[0].pk == user.pk

    results = await User.query.or_(name="Edgy").or_(name="Adam")

    assert len(results) == 2


async def test_filter_or_clause_select_new():
    user = await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Edgy", email="adam@edgy.dev")

    results = await User.query.or_({"name": "Test"}, {"name": "Adam"})

    assert len(results) == 1
    assert results[0].pk == user.pk

    results = await User.query.or_({"name": "Edgy"}, {"name": "Adam"})

    assert len(results) == 2


async def test_filter_or_clause_mixed():
    user = await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Edgy", email="adam@edgy.dev")

    results = await User.query.or_(name="Adam", email=user.email).and_(id=user.id)

    assert len(results) == 1
    assert results[0].pk == user.pk
