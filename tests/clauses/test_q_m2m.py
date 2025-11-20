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


class Role(edgy.StrictModel):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Category(edgy.StrictModel):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Product(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    role = edgy.ForeignKey(Role, null=True)
    categories = edgy.ManyToManyField(Category)

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


async def test_q_m2m_simple_or_on_products():
    """
    Q(products__name__icontains=...) over a ManyToMany should work
    and return distinct users.
    """
    adam = await User.query.create(name="Adam", email="adam@edgy.dev")
    bob = await User.query.create(name="Bob", email="bob@example.com")

    soap = await Product.query.create(name="soap")
    potatos = await Product.query.create(name="potatos")
    other = await Product.query.create(name="other")

    await adam.products.add(soap)
    await adam.products.add(potatos)
    await bob.products.add(other)

    expr = Q(products__name__icontains="soap") | Q(products__name__icontains="potatos")

    results = await User.query.filter(expr).distinct("id")

    assert {u.pk for u in results} == {adam.pk}


async def test_q_m2m_nested_role_lookup():
    """
    Q(products__role__name__icontains=...) should traverse
    User -> products (M2M) -> role (FK).
    """
    adam = await User.query.create(name="Adam", email="adam@edgy.dev")
    bob = await User.query.create(name="Bob", email="bob@example.com")

    shelf = await Role.query.create(name="shelf")
    other_role = await Role.query.create(name="floor")

    prod1 = await Product.query.create(name="soap", role=shelf)
    prod2 = await Product.query.create(name="potatos", role=other_role)

    await adam.products.add(prod1)
    await bob.products.add(prod2)

    expr = Q(products__role__name__icontains="shelf")

    results = await User.query.filter(expr).distinct("id")

    assert {u.pk for u in results} == {adam.pk}


async def test_q_m2m_multi_hop_categories():
    """
    User -> products (M2M) -> categories (M2M) with Q(products__categories__name=...).
    """
    adam = await User.query.create(name="Adam", email="adam@edgy.dev")
    bob = await User.query.create(name="Bob", email="bob@example.com")

    food = await Category.query.create(name="food")
    tools = await Category.query.create(name="tools")

    prod1 = await Product.query.create(name="soap")
    prod2 = await Product.query.create(name="hammer")

    await prod1.categories.add(food)
    await prod2.categories.add(tools)

    await adam.products.add(prod1)
    await bob.products.add(prod2)

    expr = Q(products__categories__name="food")

    results = await User.query.filter(expr).distinct("id")

    assert {u.pk for u in results} == {adam.pk}


async def test_q_m2m_nested_q_tree():
    """
    (Q(products__name__icontains='soap') | Q(products__role__name='shelf'))
    & Q(email__icontains='edgy')
    """
    adam = await User.query.create(name="Adam", email="adam@edgy.dev")
    other_user = await User.query.create(name="Other", email="other@example.com")

    shelf = await Role.query.create(name="shelf")
    other_role = await Role.query.create(name="floor")

    soap = await Product.query.create(name="soap", role=shelf)
    other_prod = await Product.query.create(name="other", role=other_role)

    await adam.products.add(soap)
    await other_user.products.add(other_prod)

    inner = Q(products__name__icontains="soap") | Q(products__role__name="shelf")
    expr = Q(inner) & Q(email__icontains="edgy")

    results = await User.query.filter(expr).distinct("id")

    assert {u.pk for u in results} == {adam.pk}


async def test_q_m2m_combined_with_user_fields():
    """
    Combine M2M-based Q with direct field Q.
    """
    adam = await User.query.create(name="Adam", email="adam@edgy.dev")
    bob = await User.query.create(name="Adam", email="other@example.com")

    soap = await Product.query.create(name="soap")
    other_prod = await Product.query.create(name="other")

    await adam.products.add(soap)
    await bob.products.add(other_prod)

    expr = Q(name="Adam") & Q(products__name__icontains="soap")

    results = await User.query.filter(expr).distinct("id")

    assert {u.pk for u in results} == {adam.pk}


async def test_q_m2m_equivalence_to_or_chain():
    """
    Q-based expression with M2M is equivalent to chain-style or_.
    """
    adam = await User.query.create(name="Adam", email="adam@edgy.dev")
    bob = await User.query.create(name="Bob", email="bob@example.com")

    soap = await Product.query.create(name="soap")
    potatos = await Product.query.create(name="potatos")
    other = await Product.query.create(name="other")

    await adam.products.add(soap)
    await adam.products.add(potatos)
    await bob.products.add(other)

    expr = Q(products__name__icontains="soap") | Q(products__name__icontains="potatos")
    q_results = await User.query.filter(expr).distinct("id")

    chain_results = await (
        User.query.or_(products__name__icontains="soap")
        .or_(products__name__icontains="potatos")
        .distinct("id")
    )

    assert {u.pk for u in q_results} == {u.pk for u in chain_results}
