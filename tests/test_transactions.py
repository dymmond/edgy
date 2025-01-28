import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@User.transaction(force_rollback=True)
async def transaction_method(user):
    assert user.name == "edgy"
    await user.save(values={"name": "edgy2"})
    assert user.name == "edgy2"


@User.transaction(force_rollback=True)
async def transaction_method2(user):
    assert user.name == "edgy"
    user.name = "edgy2"
    await user.save()
    assert user.name == "edgy2"


@pytest.mark.parametrize("force_rollback", [True, False])
async def test_transactions(force_rollback):
    with database.force_rollback(force_rollback):
        async with models:
            user = await User.query.create(name="edgy")
            async with User.transaction(force_rollback=True):
                await user.save(values={"name": "edgy2"})
                assert user.name == "edgy2"
            await user.load()
            assert user.name == "edgy"
            async with user.transaction(force_rollback=True):
                await user.save(values={"name": "edgy2"})
                assert user.name == "edgy2"
            await user.load()
            assert user.name == "edgy"


@pytest.mark.parametrize("force_rollback", [True, False])
async def test_transactions_defer(force_rollback):
    with database.force_rollback(force_rollback):
        async with models:
            user = await User.query.create(name="edgy")
            async with User.transaction(force_rollback=True):
                user = await User.query.defer("name").get()
                await user.save(values={"name": "edgy2"})
                assert user.name == "edgy2"
            async with User.transaction(force_rollback=True):
                user = await User.query.defer("name").get()
                assert user.name == "edgy"
                user.name = "edgy2"
                await user.save()
                assert user.name == "edgy2"
            await user.load()
            assert user.name == "edgy"


@pytest.mark.parametrize("method", [transaction_method, transaction_method2])
@pytest.mark.parametrize("force_rollback", [True, False])
async def test_transactions_fn(force_rollback, method):
    with database.force_rollback(force_rollback):
        async with models:
            user = await User.query.create(name="edgy")
            await method(user)
            await user.load()
            assert user.name == "edgy"


@pytest.mark.parametrize("method", [transaction_method, transaction_method2])
@pytest.mark.parametrize("force_rollback", [True, False])
async def test_transactions_fn_defer(force_rollback, method):
    with database.force_rollback(force_rollback):
        async with models:
            user = await User.query.create(name="edgy")
            await method(await User.query.defer("name").get())
            await user.load()
            assert user.name == "edgy"
