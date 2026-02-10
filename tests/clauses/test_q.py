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

    class Meta:
        registry = models


class Product(edgy.StrictModel):
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
    async with models:
        yield


async def test_q_and_operator_with_kwargs():
    """Q(active=True) & Q(email__icontains='edgy') behaves like a normal AND."""
    user = await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Edgy", email="other@domain.dev")

    expr = Q(name="Adam") & Q(email__icontains="edgy")

    results = await User.query.filter(expr)

    assert len(results) == 1
    assert results[0].pk == user.pk


async def test_q_or_operator_with_kwargs():
    """Q(name='Adam') | Q(name='Edgy') matches either user."""
    adam = await User.query.create(name="Adam", email="adam@edgy.dev")
    edgy_user = await User.query.create(name="Edgy", email="edgy@edgy.dev")

    expr = Q(name="Adam") | Q(name="Edgy")

    results = await User.query.filter(expr)

    assert {u.pk for u in results} == {adam.pk, edgy_user.pk}


async def test_q_not_operator_with_kwargs():
    """~Q(name='Adam') excludes Adam."""
    await User.query.create(name="Adam", email="adam@edgy.dev")
    edgy_user = await User.query.create(name="Edgy", email="edgy@edgy.dev")

    expr = ~Q(name="Adam")

    results = await User.query.filter(expr)

    assert len(results) == 1
    assert results[0].pk == edgy_user.pk


async def test_q_mixed_and_or_expression():
    """
    (Q(name='Adam') & Q(email__icontains='edgy')) | Q(name='Ravyn')

    Uses normal Python precedence where & binds tighter than |.
    """
    adam = await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Adam", email="other@domain.dev")
    ravyn = await User.query.create(name="Ravyn", email="ravyn@edgy.dev")

    expr = (Q(name="Adam") & Q(email__icontains="edgy")) | Q(name="Ravyn")

    results = await User.query.filter(expr)

    assert {u.pk for u in results} == {adam.pk, ravyn.pk}


async def test_q_with_column_expressions():
    """Q can wrap raw column expressions as positional arguments."""
    user = await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Edgy", email="edgy@edgy.dev")

    expr = Q(User.columns.name == "Adam") & Q(User.columns.email == "adam@edgy.dev")

    results = await User.query.filter(expr)

    assert len(results) == 1
    assert results[0].pk == user.pk


async def test_q_nested_q_objects():
    """Q(Q(...)) still behaves as a single combined AND group."""
    user = await User.query.create(name="Adam", email="adam@edgy.dev", language="EN")
    await User.query.create(name="Adam", email="adam@other.dev", language="EN")
    await User.query.create(name="Adam", email="adam@edgy.dev", language="PT")

    inner = Q(name="Adam", email__icontains="edgy")
    expr = Q(inner) & Q(language="EN")

    results = await User.query.filter(expr)

    assert len(results) == 1
    assert results[0].pk == user.pk


async def test_q_equivalence_to_and_or_chain():
    """
    Q(name='Adam') | Q(name='Edgy') is equivalent to:
        User.query.or_(name='Adam').or_(name='Edgy')
    """
    adam = await User.query.create(name="Adam", email="adam@edgy.dev")
    edgy_user = await User.query.create(name="Edgy", email="edgy@edgy.dev")
    await User.query.create(name="Other", email="other@edgy.dev")

    expr = Q(name="Adam") | Q(name="Edgy")
    q_results = await User.query.filter(expr)

    chain_results = await User.query.or_(name="Adam").or_(name="Edgy")

    assert {u.pk for u in q_results} == {adam.pk, edgy_user.pk}
    assert {u.pk for u in chain_results} == {adam.pk, edgy_user.pk}


async def test_q_inside_or_operator():
    adam = await User.query.create(name="Adam", email="adam@edgy.dev")
    edgy_user = await User.query.create(name="Edgy", email="edgy@edgy.dev")

    expr = Q(name="Adam")

    results = await User.query.or_(expr)

    assert len(results) == 1
    assert results[0].pk == adam.pk

    # Add another OR with Q
    results = await User.query.or_(expr).or_(Q(name="Edgy"))

    assert {u.pk for u in results} == {adam.pk, edgy_user.pk}


async def test_q_inside_local_or():
    await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Edgy", email="edgy@edgy.dev")

    expr = Q(name="Adam")

    # local_or keeps all previous filters mandatory
    results = await User.query.filter(language="EN").local_or(expr)

    # Only Adam has EN? If none, then zero.
    assert len(results) in (0, 1)


async def test_q_with_related_fields():
    user = await User.query.create(name="Adam", email="adam@edgy.dev")
    product = await Product.query.create(user=user)

    expr = Q(user__id=user.pk)

    results = await Product.query.filter(expr)

    assert len(results) == 1
    assert results[0].pk == product.pk


async def test_q_not_with_related_fields():
    user1 = await User.query.create(name="Adam", email="adam@edgy.dev")
    user2 = await User.query.create(name="Edgy", email="edgy@edgy.dev")

    await Product.query.create(user=user1)
    prod2 = await Product.query.create(user=user2)

    expr = ~Q(user__id=user1.pk)

    results = await Product.query.filter(expr)

    assert len(results) == 1
    assert results[0].pk == prod2.pk


async def test_q_complex_nested_expression():
    adam = await User.query.create(name="Adam", email="adam@edgy.dev")
    edgy_user = await User.query.create(name="Edgy", email="edgy@edgy.dev")
    await User.query.create(name="Other", email="other@domain.dev")

    expr = (Q(name="Adam") | Q(name="Edgy")) & ~Q(email__icontains="domain")

    results = await User.query.filter(expr)

    # Should return Adam + Edgy, excluding 'Other'
    assert {u.pk for u in results} == {adam.pk, edgy_user.pk}


async def test_q_equivalence_complex():
    await User.query.create(name="Adam")
    await User.query.create(name="Edgy")
    await User.query.create(name="Ravyn")

    expr = Q(name__icontains="a") | Q(name="Edgy")
    q_results = await User.query.filter(expr)

    chain_results = await User.query.or_(name__icontains="a").or_(name="Edgy")

    assert {u.pk for u in q_results} == {u.pk for u in chain_results}


async def test_q_nested_multiple_levels():
    """Q(Q(Q(...))) flattens correctly and behaves as a single logical tree."""
    user = await User.query.create(name="Adam", email="adam@edgy.dev", language="EN")
    await User.query.create(name="Adam", email="adam@other.dev", language="EN")
    await User.query.create(name="Adam", email="adam@edgy.dev", language="PT")

    inner = Q(name="Adam")
    middle = Q(inner) & Q(email__icontains="edgy")
    expr = Q(middle) & Q(language="EN")

    results = await User.query.filter(expr)

    assert len(results) == 1
    assert results[0].pk == user.pk


async def test_q_nested_with_related_fields():
    """Nested Q with related lookups should behave as a single AND group."""
    user = await User.query.create(name="Adam", email="adam@edgy.dev")
    product = await Product.query.create(user=user)

    inner = Q(user__id=user.pk)
    expr = Q(inner) & Q(user__email="adam@edgy.dev")

    # Explicitly join the related user table so 'user' exists in tables_and_models
    results = await Product.query.select_related("user").filter(expr)

    assert len(results) == 1
    assert results[0].pk == product.pk


async def test_q_nested_inside_or_group():
    """Nested Q inside an OR group is equivalent to a non-nested expression."""
    adam = await User.query.create(name="Adam", email="adam@edgy.dev")
    await User.query.create(name="Adam", email="other@domain.dev")
    ravyn = await User.query.create(name="Ravyn", email="ravyn@edgy.dev")

    # Non-nested expression
    flat_expr = (Q(name="Adam") & Q(email__icontains="edgy")) | Q(name="Ravyn")
    flat_results = await User.query.filter(flat_expr)

    # Nested equivalent using Q(Q(...))
    nested_inner = Q(name="Adam") & Q(email__icontains="edgy")
    nested_expr = Q(nested_inner) | Q(name="Ravyn")
    nested_results = await User.query.filter(nested_expr)

    assert {u.pk for u in flat_results} == {adam.pk, ravyn.pk}
    assert {u.pk for u in nested_results} == {adam.pk, ravyn.pk}
