import datetime
import decimal
from enum import Enum

import pytest
import sqlalchemy

import edgy
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


def time():
    return datetime.datetime.now().time()


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


class SimpleProduct(edgy.StrictModel):
    active = fields.BooleanField(null=True)
    description = fields.CharField(null=True, max_length=255)
    integer = fields.IntegerField(null=True)
    price = fields.DecimalField(max_digits=9, decimal_places=2, null=True)
    value = fields.FloatField(null=True)

    class Meta:
        registry = models


class Product(edgy.StrictModel):
    active = fields.BooleanField(null=True)
    description = fields.CharField(null=True, max_length=255)
    integer = fields.IntegerField(null=True)
    price = fields.DecimalField(max_digits=9, decimal_places=2, null=True)
    value = fields.FloatField(null=True)
    binary = fields.BinaryField(null=True)
    duration = fields.DurationField(null=True)
    created = fields.DateTimeField(null=True)
    created_date = fields.DateField(null=True)
    created_time = fields.TimeField(null=True)
    uuid = fields.UUIDField(null=True)
    data = fields.JSONField(null=True)
    status = fields.ChoiceField(StatusEnum, null=True)
    manual = fields.FileField(null=True)
    ipaddress = fields.IPAddressField(null=True)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    # this creates and drops the database
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    # this rolls back
    async with models:
        yield


@pytest.mark.parametrize(
    "product,isnull",
    [
        pytest.param(SimpleProduct(), True),
        pytest.param(
            SimpleProduct(description="", integer=0, price=decimal.Decimal("0"), value=0.0), False
        ),
        pytest.param(
            SimpleProduct(description="", integer=0, price=decimal.Decimal("0.0"), value=0.0),
            False,
        ),
        pytest.param(Product(), True),
        pytest.param(
            Product(
                active=False,
                duration=datetime.timedelta(),
                description="",
                integer=0,
                price=decimal.Decimal("0.0"),
                value=0.0,
                binary=b"",
            ),
            False,
        ),
    ],
)
async def test_operators_empty(product, isnull):
    await product.save()
    isempty_queries = {}
    isnull_queries = {}
    for field_name, field in product.meta.fields.items():
        if field.primary_key or field.exclude or field_name == "manual_metadata":
            continue
        isempty_queries[f"{field_name}__isempty"] = True
        isnull_queries[f"{field_name}__isnull"] = True
    assert (await type(product).query.get(**isempty_queries)) is not None
    assert (await type(product).query.exists(**isnull_queries)) == isnull


@pytest.mark.parametrize(
    "product,isempty,isnull",
    [
        pytest.param(Product(), True, True),
        pytest.param(Product(data=sqlalchemy.null()), True, True),
        pytest.param(Product(data=sqlalchemy.JSON.NULL), True, True),
        pytest.param(Product(data=""), True, False),
        pytest.param(Product(data=[]), True, False),
        pytest.param(Product(data={}), True, False),
        pytest.param(Product(data=0), True, False),
        pytest.param(Product(data=0.0), True, False),
    ],
)
async def test_operators_empty_json(product, isempty, isnull):
    await product.save()
    isempty_queries = {"data__isempty": True}
    isnull_queries = {"data__isnull": True}
    assert (await type(product).query.exists(**isempty_queries)) == isempty
    assert (await type(product).query.exists(**isnull_queries)) == isnull

    isempty_queries = {"data__isempty": False}
    isnull_queries = {"data__isnull": False}
    assert (await type(product).query.exists(**isempty_queries)) != isempty
    assert (await type(product).query.exists(**isnull_queries)) != isnull


@pytest.mark.parametrize("field_name", ["created", "created_date", "ipaddress"])
async def test_troubled_none(field_name):
    product = await Product.query.create()
    assert await type(product).query.exists(**{field_name: None})
