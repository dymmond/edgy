import decimal
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

import pytest

import edgy
from edgy.core.db import fields
from edgy.core.signals import post_bulk, post_save, post_update, pre_bulk
from edgy.testclient import DatabaseTestClient
from edgy.testing.factory import ModelFactory
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, force_rollback=False, drop_database=True)
models = edgy.Registry(database=database)


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with models:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


async def pre_bulk_fn(sender, **kwargs):
    await Log.query.create(
        signal="pre_bulk",
        class_name=sender.__name__,
        params={k: str(v) for k, v in kwargs.items()},
    )


async def post_bulk_fn(sender, **kwargs):
    await Log.query.create(
        signal="post_bulk",
        class_name=sender.__name__,
        params={k: str(v) for k, v in kwargs.items()},
    )


async def post_save_fn(sender, **kwargs):
    await Log.query.create(
        signal="post_save",
        class_name=sender.__name__,
        params={k: str(v) for k, v in kwargs.items()},
    )


async def post_update_fn(sender, **kwargs):
    await Log.query.create(
        signal="post_update",
        class_name=sender.__name__,
        params={k: str(v) for k, v in kwargs.items()},
    )


@pytest.fixture(autouse=True, scope="function")
async def connect_signals():
    pre_bulk.connect(pre_bulk_fn, Product, weak=True)
    post_bulk.connect(post_bulk_fn, Product, weak=True)
    post_save.connect(post_save_fn, Product, weak=True)
    post_update.connect(post_update_fn, Product, weak=True)
    try:
        yield
    finally:
        pre_bulk.disconnect(pre_bulk_fn)
        post_bulk.disconnect(post_bulk_fn)
        post_save.disconnect(post_save_fn)
        post_update.disconnect(post_update_fn)


def time():
    return datetime.now().time()


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


class Product(edgy.StrictModel):
    id: int = fields.IntegerField(primary_key=True, autoincrement=True)
    uuid: UUID = fields.UUIDField(null=True, unique=True)
    created: datetime = fields.DateTimeField(default=datetime.now)
    created_day: datetime = fields.DateField(default=date.today)
    created_time: datetime = fields.TimeField(default=time)
    created_date: datetime = fields.DateField(auto_now_add=True)
    created_datetime: datetime = fields.DateTimeField(auto_now_add=True)
    updated_datetime: datetime = fields.DateTimeField(auto_now=True)
    updated_date: datetime = fields.DateField(auto_now=True)
    data: dict[Any, Any] = fields.JSONField(default=dict)
    description: str = fields.CharField(null=True, max_length=255)
    huge_number: int = fields.BigIntegerField(default=0)
    price: decimal.Decimal = fields.DecimalField(max_digits=9, decimal_places=2, null=True)
    status: str = fields.ChoiceField(StatusEnum, default=StatusEnum.DRAFT)
    value: float = fields.FloatField(null=True)

    class Meta:
        registry = models


class ProductFactory(ModelFactory):
    class Meta:
        model = Product


class Log(edgy.StrictModel):
    signal = edgy.CharField(max_length=255)
    class_name = edgy.CharField(max_length=255)
    params = edgy.JSONField()

    class Meta:
        registry = models

    def __str__(self) -> str:
        return str(self.extract_db_fields())

    def __repr__(self) -> str:
        return f"Log<{self}>"


async def test_calibrate():
    factory = ProductFactory(price=None, uuid=None)
    product = await factory.build(overwrites={"created_time": time()}).save()
    await product.update(name="saffier")
    await Product.query.update(name="edgy")
    logs = await Log.query.all()
    assert len(logs) == 3
    assert logs[0].signal == "post_save"
    assert logs[1].signal == "post_update"
    assert logs[2].signal == "post_update"


@pytest.mark.parametrize("method", ["bulk_create", "bulk_update_or_create", "bulk_get_or_create"])
async def test_bulk_create_like(method):
    factory = ProductFactory(price=None, uuid=None)
    inputs = [factory.build(overwrites={"created_time": time()}) for i in range(100)]
    await getattr(Product.query, method)(inputs)
    logs = await Log.query.all()
    assert all(log.signal in {"pre_bulk", "post_bulk"} for log in logs)
    assert len(logs) == 2


async def test_bulk_create_bulk_ignore():
    factory = ProductFactory(price=None, uuid=None)
    inputs = [factory.build(overwrites={"created_time": time()}) for i in range(100)]
    await Product.query.bulk_create(inputs, ignore_conflicts=True)
    logs = await Log.query.all()
    assert all(log.signal in {"pre_bulk", "post_bulk"} for log in logs)
    assert len(logs) == 2


@pytest.mark.parametrize("rollback", [True, False])
@pytest.mark.parametrize("method", ["bulk_update", "bulk_update_or_create"])
async def test_bulk_update_like(method, rollback):
    factory = ProductFactory(price=None, uuid=None)
    await Product.query.bulk_create(
        [factory.build(overwrites={"created_time": time()}) for i in range(100)]
    )
    logs = await Log.query.all()
    assert all(log.signal in {"pre_bulk", "post_bulk"} for log in logs)
    assert len(logs) == 2
    products1 = await Product.query.order_by("id").distinct()
    inputs2 = [
        factory.build(overwrites={"id": products1[i].id, "created_time": time()})
        for i in range(50)
    ]
    with database.force_rollback(rollback):
        products2 = await getattr(Product.query, method)(inputs2)
        products = await Product.query.order_by("id").distinct()
        logs = await Log.query.all()
    assert len(products) == 100
    for i in range(100):
        if i < 50:
            assert (
                products[i] == products2[i][0] if isinstance(products2[i], tuple) else products2[i]
            )
        else:
            assert products[i] == products1[i]
    assert all(log.signal in {"pre_bulk", "post_bulk"} for log in logs)
    assert len(logs) == 4
