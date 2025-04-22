import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class MyWebsite(edgy.StrictModel):
    rev: int = edgy.IntegerField(increment_on_save=1, default=0)

    class Meta:
        registry = models


class MyRevSafe(edgy.StrictModel):
    name = edgy.CharField(max_length=50)
    document: edgy.files.FieldFile = edgy.fields.FileField(null=True)
    id: int = edgy.BigIntegerField(primary_key=True, autoincrement=True)
    rev: int = edgy.IntegerField(increment_on_save=1, primary_key=True, default=1)

    class Meta:
        registry = models


class MyRevUnsafe(edgy.StrictModel):
    name = edgy.CharField(max_length=50)
    document: edgy.files.FieldFile = edgy.fields.FileField(null=True)
    id: int = edgy.BigIntegerField(primary_key=True, autoincrement=True)
    rev: int = edgy.IntegerField(increment_on_save=1, primary_key=True, default=1, read_only=False)

    class Meta:
        registry = models


class MyCountdown(edgy.StrictModel):
    name = edgy.CharField(max_length=50)
    rev: int = edgy.IntegerField(increment_on_save=-1, default=10, read_only=False)

    class Meta:
        registry = models


class MyCountdownNoDefault(edgy.StrictModel):
    name = edgy.CharField(max_length=50)
    rev: int = edgy.IntegerField(increment_on_save=-1, read_only=False)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    # this creates and drops the database
    async with database:
        await models.create_all()
        yield
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    # this rolls back
    async with models:
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
    obj = await MyRevSafe.query.create(
        name="foo", document=edgy.files.ContentFile(b"foo", name="foo.bytes")
    )
    assert obj.rev == 1
    await obj.save(values={"document": edgy.files.ContentFile(b"bar", name="foo.bytes")})
    assert obj.rev == 2
    objs = await MyRevSafe.query.all()
    assert len(objs) == 2
    assert objs[0].rev == 1
    assert objs[0].document.open().read() == b"foo"
    assert objs[1].rev == 2
    assert objs[1].document.open().read() == b"bar"
    objs[0].document.delete(instant=True)
    objs[1].document.delete(instant=True)


async def test_rev_unsafe_with_document():
    obj = await MyRevUnsafe.query.create(
        name="foo", document=edgy.files.ContentFile(b"foo", name="foo.bytes")
    )
    old_name = obj.document.name
    assert obj.document
    assert obj.rev == 1
    await obj.save()
    assert obj.rev == 2
    assert obj.document.name != old_name
    objs = await MyRevUnsafe.query.all()
    assert len(objs) == 2
    assert objs[0].rev == 1
    assert objs[0].document.open().read() == b"foo"
    assert objs[1].rev == 2
    assert objs[1].document.open().read() == b"foo"
    # it shall fail
    with pytest.raises(IntegrityError):
        await obj.update(name="bar")
    # revision unsafe update
    await obj.update(
        name="bar", rev=obj.rev, document=edgy.files.ContentFile(b"zar", name="foo.bytes")
    )
    assert obj.rev == 2
    await objs[0].load()
    assert objs[0].document.open().read() == b"foo"
    await objs[1].load()
    assert objs[1].document.open().read() == b"zar"
    objs[0].document.delete(instant=True)
    objs[1].document.delete(instant=True)


async def test_rev_unsafe_with_document_old_way():
    obj = await MyRevUnsafe.query.create(
        name="foo", document=edgy.files.ContentFile(b"foo", name="foo.bytes")
    )
    old_name = obj.document.name
    assert obj.document
    assert obj.rev == 1
    fileobj = obj.document.to_file()
    await obj.save(values={"document": fileobj})
    assert obj.rev == 2
    assert obj.document.name != old_name
    objs = await MyRevUnsafe.query.all()
    assert len(objs) == 2
    assert objs[0].rev == 1
    assert objs[0].document.open().read() == b"foo"
    assert objs[1].rev == 2
    assert objs[1].document.open().read() == b"foo"
    # it shall fail
    with pytest.raises(IntegrityError):
        await obj.update(name="bar")
    # revision unsafe update
    await obj.update(
        name="bar", rev=obj.rev, document=edgy.files.ContentFile(b"zar", name="foo.bytes")
    )
    assert obj.rev == 2
    await objs[0].load()
    assert objs[0].document.open().read() == b"foo"
    await objs[1].load()
    assert objs[1].document.open().read() == b"zar"
    objs[0].document.delete(instant=True)
    objs[1].document.delete(instant=True)


async def test_rev_unsafe_without_document():
    obj = await MyRevUnsafe.query.create(name="foo")
    assert obj.rev == 1
    await obj.save()
    assert obj.rev == 2
    objs = await MyRevUnsafe.query.all()
    assert len(objs) == 2
    assert objs[0].rev == 1
    assert not objs[0].document
    assert objs[1].rev == 2
    assert not objs[1].document
    # it shall fail
    with pytest.raises(IntegrityError):
        await obj.update(name="bar")
    # revision unsafe update
    await obj.update(
        name="bar", rev=obj.rev, document=edgy.files.ContentFile(b"zar", name="foo.bytes")
    )
    assert obj.rev == 2
    await objs[1].load()
    assert objs[1].document.open().read() == b"zar"
    objs[0].document.delete(instant=True)
    objs[1].document.delete(instant=True)


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
