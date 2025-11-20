import pytest

import edgy
from edgy.core.db.querysets.clauses import Q
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)
    email = edgy.EmailField(null=True, max_length=255)
    products = edgy.ManyToManyField("Product")

    class Meta:
        registry = models


class Product(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    role = edgy.ForeignKey("Role", null=True)

    class Meta:
        registry = models


class Role(edgy.StrictModel):
    name = edgy.CharField(max_length=100)

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


async def test_q_and_operator_with_kwargs():
    """Q(active=True) & Q(email__icontains='edgy') behaves like a normal AND."""
    user = await User.query.create(name="Adam", email="adam@edgy.dev")
    role = await Role.query.create(name="shelf")
    prod = await Product.query.create(name="soap")
    prod2 = await Product.query.create(name="potatos", role=role)

    await user.products.add(prod)
    await user.products.add(prod2)

    expr = (
        Q(name="Adam")
        | Q(products__name__icontains="soap")
        | Q(products__role__name__icontains="shelf")
    )

    results = await User.query.filter(expr).distinct("id")

    assert len(results) == 1
