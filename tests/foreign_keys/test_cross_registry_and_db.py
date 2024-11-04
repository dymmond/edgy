import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_ALTERNATIVE_URL, DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
database2 = DatabaseTestClient(DATABASE_ALTERNATIVE_URL, full_isolation=False)
modelsa = edgy.Registry(database=database)
modelsb = edgy.Registry(database=database2)
modelsc = edgy.Registry(database=database)


class ObjectA(edgy.StrictModel):
    self_ref = edgy.ForeignKey("ObjectA", on_delete=edgy.CASCADE, null=True)
    c = edgy.ForeignKey("ObjectC", target_registry=modelsc, on_delete=edgy.CASCADE, null=True)

    class Meta:
        registry = modelsa


class ObjectB(edgy.StrictModel):
    a = edgy.ForeignKey(ObjectA, on_delete=edgy.CASCADE, null=True)

    class Meta:
        registry = modelsb


class ObjectC(edgy.StrictModel):
    b = edgy.ForeignKey(ObjectB, on_delete=edgy.CASCADE, null=True)

    class Meta:
        registry = modelsc


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database, database2:
        await modelsc.create_all()
        await modelsb.create_all()
        await modelsa.create_all()
        yield
        if not database.drop:
            await modelsa.drop_all()
            await modelsc.drop_all()

        if not database.drop:
            await modelsb.drop_all()


async def test_specs():
    assert not ObjectA.meta.fields["self_ref"].is_cross_db()
    assert not ObjectA.meta.fields["c"].is_cross_db()
    assert ObjectB.meta.fields["a"].is_cross_db()
    assert ObjectC.meta.fields["b"].is_cross_db()


async def test_empty_fk():
    obj = await ObjectA.query.create()
    assert obj.self_ref is None
    assert obj.c is None
    obj = await ObjectB.query.create(a={})
    assert obj.a.self_ref is None
    assert obj.a.c is None


async def test_create():
    obj = await ObjectC.query.create(b={"a": {"c": None, "self_ref": None}})
    # assert obj.b.a.self_ref is None
    obj.b.a.self_ref = obj.b.a
    obj.b.a.c = obj
    await obj.b.a.save()
    loaded = await ObjectC.query.get(pk=obj.pk)
    assert loaded.id == obj.id
    assert loaded.b.id == obj.b.id
    assert loaded.b.a.meta.registry is modelsa
    assert loaded.b.a.id == obj.b.a.id
    assert loaded.b.a.c == obj


async def test_query():
    obj = await ObjectC.query.create(b={"a": {"c": None, "self_ref": None}})
    # assert obj.b.a.self_ref is None
    obj.b.a.c = obj
    obj.b.a.self_ref = obj.b.a
    await obj.b.a.save()
    objs = await ObjectC.query.filter(b__a__c=obj)
    assert objs[0] == obj
