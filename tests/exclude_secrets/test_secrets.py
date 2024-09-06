import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class Main(edgy.Model):
    name = edgy.CharField(max_length=255)

    class Meta:
        registry = models


class User(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    name = edgy.CharField(max_length=100)
    age = edgy.IntegerField(secret=True)
    language = edgy.CharField(max_length=200, null=True, secret=True)
    main = edgy.ForeignKey(Main, related_name="users", secret=True, null=True)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
    await models.drop_all()


async def test_exclude_secrets():
    await User.query.create(name="Edgy", age=2, language="EN")
    await User.query.create(name="Saffier", age=2, language="EN")

    results = await User.query.filter(id=1).exclude_secrets()

    assert len(results) == 1

    user = results[0]

    assert user.model_dump() == {"id": 1, "name": "Edgy"}

    results = await User.query.exclude_secrets().get(id=2)

    assert results.model_dump() == {"id": 2, "name": "Saffier"}


async def test_exclude_secrets_fk():
    main = await Main.query.create(name="main")
    await User.query.create(name="Edgy", age=2, language="EN", main=main)

    results = await User.query.filter(id=1).exclude_secrets()

    assert len(results) == 1

    user = results[0]

    assert user.model_dump() == {"id": 1, "name": "Edgy"}


async def test_exclude_secrets_filter():
    main = await Main.query.create(name="main")
    await User.query.create(name="Edgy", age=2, language="EN", main=main)

    results = await User.query.filter(id=1).exclude_secrets()

    assert len(results) == 1

    user = results[0]

    assert user.model_dump() == {"id": 1, "name": "Edgy"}


async def test_exclude_secrets_various():
    main = await Main.query.create(name="main")
    await User.query.create(name="Edgy", age=2, language="EN", main=main)

    results = await User.query.only("id").exclude_secrets()

    assert len(results) == 1

    user = results[0]

    assert user.model_dump() == {"id": 1}


async def test_exclude_secrets_undo():
    main = await Main.query.create(name="main")
    await User.query.create(name="Edgy", age=2, language="EN", main=main)

    results = await User.query.exclude_secrets().exclude_secrets(False)

    assert len(results) == 1

    user = results[0]
    await user.load_recursive()

    assert user.model_dump() == {
        "age": 2,
        "id": 1,
        "language": "EN",
        "main": {"id": 1, "name": "main"},
        "name": "Edgy",
    }
