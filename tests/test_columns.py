import datetime
import decimal
import ipaddress
import uuid
from enum import Enum

import pytest

import edgy
from edgy.core.db import fields
from edgy.exceptions import FieldDefinitionError
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


class Product(edgy.StrictModel):
    id = fields.IntegerField(primary_key=True, autoincrement=True)
    uuid = fields.UUIDField(null=True)
    created = fields.DateTimeField(default=datetime.datetime.now, with_timezone=False)
    created_day = fields.DateField(default=datetime.date.today)
    created_time = fields.TimeField(default=time)
    created_date = fields.DateField(auto_now_add=True, with_timezone=False)
    created_datetime = fields.DateTimeField(auto_now_add=True, with_timezone=False)
    updated_datetime = fields.DateTimeField(auto_now=True, with_timezone=False)
    updated_date = fields.DateField(auto_now=True)
    data = fields.JSONField(default=dict)
    description = fields.CharField(null=True, max_length=255)
    huge_number = fields.BigIntegerField(default=0)
    price = fields.DecimalField(max_digits=9, decimal_places=2, null=True)
    status = fields.ChoiceField(StatusEnum, default=StatusEnum.DRAFT)
    status2 = fields.CharChoiceField(StatusEnum, default=StatusEnum.DRAFT)
    value = fields.FloatField(null=True)

    class Meta:
        registry = models


class User(edgy.StrictModel):
    id = fields.UUIDField(primary_key=True, default=uuid.uuid4)
    name = fields.CharField(null=True, max_length=16)
    email = fields.EmailField(null=True, max_length=256)
    ipaddress = fields.IPAddressField(null=True)
    url = fields.URLField(null=True, max_length=2048)
    password = fields.PasswordField(null=True, max_length=255)

    class Meta:
        registry = models


class Customer(edgy.StrictModel):
    name = fields.CharField(null=True, max_length=16)

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


async def test_model_crud():
    # fails e.g. at 2024-09-27T23:17:53+00:00 when not having with_timezone=False
    # why? the database starts to inject a timezone when none is set
    # strangely this doesn't happen with tests/models/test_datetime.py
    product = await Product.query.create()
    product = await Product.query.get(pk=product.pk)
    assert product.created.year == datetime.datetime.now().year
    assert product.meta.fields["created"].get_default_value().tzinfo is None
    assert product.created.tzinfo is None
    assert product.created_day == datetime.date.today()
    assert product.created_date == datetime.date.today()
    assert product.created_datetime.tzinfo is None
    assert product.created_datetime.date() == datetime.datetime.now().date()
    assert product.updated_date == datetime.date.today()
    assert product.updated_datetime.date() == datetime.datetime.now().date()
    assert product.data == {}
    assert product.description is None
    assert product.huge_number == 0
    assert product.price is None
    assert product.status == StatusEnum.DRAFT
    assert product.status2 == StatusEnum.DRAFT
    assert product.value is None
    assert product.uuid is None

    await product.update(
        data={"foo": 123},
        value=123.456,
        status=StatusEnum.RELEASED,
        status2=StatusEnum.RELEASED,
        price=decimal.Decimal("999.99"),
        uuid=uuid.UUID("f4e87646-bafa-431e-a0cb-e84f2fcf6b55"),
    )

    product = await Product.query.get()
    assert product.value == 123.456
    assert product.data == {"foo": 123}
    assert product.status == StatusEnum.RELEASED
    assert product.status2 == StatusEnum.RELEASED
    assert product.price == decimal.Decimal("999.99")
    assert product.uuid == uuid.UUID("f4e87646-bafa-431e-a0cb-e84f2fcf6b55")

    last_updated_datetime = product.updated_datetime
    last_updated_date = product.updated_date
    user = await User.query.create()
    assert isinstance(user.pk, uuid.UUID)

    user = await User.query.get()
    assert user.email is None
    assert user.ipaddress is None
    assert user.url is None

    await user.update(
        ipaddress="192.168.1.1",
        name="Test",
        email="test@edgy.com",
        url="https://edgy.com",
        password="12345",
    )

    user = await User.query.get()
    assert isinstance(user.ipaddress, (ipaddress.IPv4Address, ipaddress.IPv6Address))
    assert user.password == "12345"

    assert user.url == "https://edgy.com/"
    await product.update(data={"foo": 1234})
    assert product.updated_datetime != last_updated_datetime
    assert product.updated_date == last_updated_date


async def test_both_auto_now_and_auto_now_add_raise_error():
    with pytest.raises(FieldDefinitionError):

        class Product(edgy.StrictModel):
            created_datetime = (fields.DateTimeField(auto_now_add=True, auto_now=True),)

            class Meta:
                registry = models

        await Product.query.create()


async def test_pk_auto_increments():
    customer = await Customer.query.create(name="test")
    customers = await Customer.query.all()

    assert customer.pk == 1
    assert customers[0].pk == 1

    await customer.delete()

    customer = await Customer.query.create(name="test")
    customers = await Customer.query.all()

    assert customer.pk == 2
    assert customers[0].pk == 2

    assert len(customers) == 1
