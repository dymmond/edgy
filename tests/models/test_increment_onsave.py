import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class MyWebsite(edgy.Model):
    rev: int = edgy.IntegerField(increment_on_save=1, default=0)

    class Meta:
        registry = models


class MyRevSafe(edgy.Model):
    name = edgy.CharField(max_length=50)
    id: int = edgy.BigIntegerField(primary_key=True, autoincrement=True)
    rev: int = edgy.IntegerField(increment_on_save=1, primary_key=True, default=1)

    class Meta:
        registry = models


class MyRevUnsafe(edgy.Model):
    name = edgy.CharField(max_length=50)
    id: int = edgy.BigIntegerField(primary_key=True, autoincrement=True)
    rev: int = edgy.IntegerField(increment_on_save=1, primary_key=True, default=1, read_only=False)

    class Meta:
        registry = models


class MyCountdown(edgy.Model):
    name = edgy.CharField(max_length=50)
    rev: int = edgy.IntegerField(increment_on_save=-1, default=10, read_only=False)

    class Meta:
        registry = models


class MyCountdownNoDefault(edgy.Model):
    name = edgy.CharField(max_length=50)
    rev: int = edgy.IntegerField(increment_on_save=-1, read_only=False)

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


async def test_website():
    await MyWebsite.query.bulk_create([{"id": 1}, {"id": 2}])
    websites = await MyWebsite.query.all()
    assert websites[0].rev == 0
    assert websites[1].rev == 0
    await websites[0].save()
    assert websites[0].rev == 1
    await websites[1].load()
    assert websites[1].rev == 0
    with pytest.raises(IntegrityError):
        await websites[0].save(force_insert=True)

    await websites[0].load()
    assert websites[0].rev == 1


async def test_rev_safe():
    obj = await MyRevSafe.query.create(name="foo")
    assert obj.rev == 1
    await obj.save()
    assert obj.rev == 2
    objs = await MyRevSafe.query.all()
    assert len(objs) == 2
    assert objs[0].rev == 1
    assert objs[1].rev == 2


async def test_rev_unsafe():
    obj = await MyRevUnsafe.query.create(name="foo")
    assert obj.rev == 1
    await obj.save()
    assert obj.rev == 2
    objs = await MyRevUnsafe.query.all()
    assert len(objs) == 2
    assert objs[0].rev == 1
    assert objs[1].rev == 2
    # it shall fail
    with pytest.raises(IntegrityError):
        await obj.update(name="bar")
    # revision unsafe update
    await obj.update(name="bar", rev=obj.rev)
    assert obj.rev == 2


async def test_countdown():
    obj = await MyCountdown.query.create(name="count")
    assert obj.rev == 10
    await obj.save()
    assert obj.rev == 9
    await obj.save(values={"rev": 100})
    assert obj.rev == 100


async def test_countdown_nodefault():
    with pytest.raises(ValidationError):
        await MyCountdownNoDefault.query.create(name="count")
    obj = await MyCountdownNoDefault.query.create(name="count", rev=10)
    assert obj.rev == 10
    await obj.save()
    assert obj.rev == 9
