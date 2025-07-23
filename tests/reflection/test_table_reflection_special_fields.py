import sys
from contextlib import redirect_stdout
from datetime import timedelta
from io import StringIO
from uuid import uuid4

import pytest
import sqlalchemy

import edgy
from edgy.core.db.datastructures import Index
from edgy.testclient import DatabaseTestClient
from edgy.utils.inspect import InspectDB
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database)
second = edgy.Registry(database=edgy.Database(database, force_rollback=False))
# not connected at all
third = edgy.Registry(database=edgy.Database(database, force_rollback=False))

expected_result1 = """
class Products(edgy.ReflectModel):
    name = edgy.CharField(max_length=255, null=False)
    title = edgy.CharField(max_length=255, null=True)
    price = edgy.FloatField(null=False)
    uuid = edgy.UUIDField(null=False)
    duration = edgy.DurationField(null=False)
    extra = edgy.JSONField(null=False)
    array = edgy.PGArrayField(item_type=sqlalchemy.sql.sqltypes.VARCHAR, null=False)
    id = edgy.BigIntegerField(autoincrement=True, null=False, primary_key=True)

    class Meta:
        registry = registry
        tablename = "products"
""".strip()
expected_result_full_info = """
class Products(edgy.ReflectModel):
    name = edgy.CharField(max_length=255, null=False, index=True)
    title = edgy.CharField(max_length=255, null=True)
    price = edgy.FloatField(max_digits=4, null=False)
    uuid = edgy.UUIDField(null=False)
    duration = edgy.DurationField(null=False)
    extra = edgy.JSONField(null=False)
    id = edgy.BigIntegerField(autoincrement=True, null=False, primary_key=True)

    class Meta:
        registry = registry
        tablename = "products"
""".strip()


class Product(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=255, index=True)
    title = edgy.fields.CharField(max_length=255, null=True)
    price = edgy.fields.FloatField(max_digits=4)
    uuid = edgy.fields.UUIDField(default=uuid4)
    duration = edgy.fields.DurationField()
    extra = edgy.fields.JSONField(default=dict)
    array = edgy.fields.PGArrayField(sqlalchemy.String(), default=list)

    class Meta:
        registry = models
        indexes = [Index(fields=["name", "title"], name="idx_name_title")]


class ProductThird(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=255, index=True)
    title = edgy.fields.CharField(max_length=255, null=True)
    price = edgy.fields.FloatField(max_digits=4)
    uuid = edgy.fields.UUIDField()
    duration = edgy.fields.DurationField()
    extra = edgy.fields.JSONField()

    class Meta:
        tablename = "products"
        registry = third


class ReflectedProduct(edgy.ReflectModel):
    name = edgy.fields.CharField(max_length=50)

    class Meta:
        tablename = "products"
        registry = second


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with models:
        await models.create_all()
        async with second:
            yield
        if not database.drop:
            await models.drop_all()


async def test_can_reflect_correct_columns():
    second.invalidate_models()
    assert ReflectedProduct.table.c.price.type.as_generic().__class__ == sqlalchemy.Float
    assert ReflectedProduct.table.c.uuid.type.as_generic().__class__ == sqlalchemy.Uuid
    assert ReflectedProduct.table.c.duration.type.as_generic().__class__ == sqlalchemy.Interval
    # now the tables should be initialized
    assert (
        second.metadata_by_name[None].tables["products"].c.uuid.type.as_generic().__class__
        == sqlalchemy.Uuid
    )
    assert (
        second.metadata_by_name[None].tables["products"].c.duration.type.as_generic().__class__
        == sqlalchemy.Interval
    )


async def test_create_correct_inspect_db():
    inflected = InspectDB(str(models.database.url))
    out = StringIO()
    with redirect_stdout(out):
        inflected.inspect()
    out.seek(0)
    generated = out.read()
    generated = "\n".join(generated.splitlines()[:-1])
    # remove indexes as they tend to be instable (last line)
    assert generated.strip().endswith(expected_result1)


async def test_create_correct_inspect_db_with_full_info_avail():
    # Here we generate from an original metadata a file
    # this will however not happen often
    third.refresh_metadata()
    tables, _ = InspectDB.generate_table_information(third.metadata_by_name[None])

    out = StringIO()
    with redirect_stdout(out):
        for line in InspectDB.write_output(tables, database, schema=None):
            sys.stdout.writelines(line)  # type: ignore
    out.seek(0)
    generated = out.read()
    assert generated.strip().endswith(expected_result_full_info)


async def test_can_read_update_fields():
    await Product.query.create(
        name="Ice cream", title="yummy ice cream", duration=timedelta(hours=3), price=1.4
    )

    product = await ReflectedProduct.query.get()
    assert product.name == "Ice cream"
    assert product.title == "yummy ice cream"
    assert product.duration == timedelta(hours=3)
    assert product.extra == {}
    product.name = "Chocolate"
    await product.save()

    # check first table
    old_product = await Product.query.get(pk=product)
    assert old_product.name == "Chocolate"
