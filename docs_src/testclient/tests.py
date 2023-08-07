import datetime
import decimal
import ipaddress
import uuid
from enum import Enum

import pytest
import saffier
from saffier.db.models import fields
from saffier.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, drop_database=True)
models = saffier.Registry(database=database)

pytestmark = pytest.mark.anyio


def time():
    return datetime.datetime.now().time()


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


class Product(saffier.Model):
    id = fields.IntegerField(primary_key=True)
    uuid = fields.UUIDField(null=True)
    created = fields.DateTimeField(default=datetime.datetime.now)
    created_day = fields.DateField(default=datetime.date.today)
    created_time = fields.TimeField(default=time)
    created_date = fields.DateField(auto_now_add=True)
    created_datetime = fields.DateTimeField(auto_now_add=True)
    updated_datetime = fields.DateTimeField(auto_now=True)
    updated_date = fields.DateField(auto_now=True)
    data = fields.JSONField(default={})
    description = fields.CharField(blank=True, max_length=255)
    huge_number = fields.BigIntegerField(default=0)
    price = fields.DecimalField(max_digits=5, decimal_places=2, null=True)
    status = fields.ChoiceField(StatusEnum, default=StatusEnum.DRAFT)
    value = fields.FloatField(null=True)

    class Meta:
        registry = models


class User(saffier.Model):
    id = fields.UUIDField(primary_key=True, default=uuid.uuid4)
    name = fields.CharField(null=True, max_length=16)
    email = fields.EmailField(null=True, max_length=256)
    ipaddress = fields.IPAddressField(null=True)
    url = fields.URLField(null=True, max_length=2048)
    password = fields.PasswordField(null=True, max_length=255)

    class Meta:
        registry = models


class Customer(saffier.Model):
    name = fields.CharField(null=True, max_length=16)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_transactions():
    with database.force_rollback():
        async with database:
            yield


async def test_model_crud():
    product = await Product.query.create()
    product = await Product.query.get(pk=product.pk)
    assert product.created.year == datetime.datetime.now().year
    assert product.created_day == datetime.date.today()
    assert product.created_date == datetime.date.today()
    assert product.created_datetime.date() == datetime.datetime.now().date()
    assert product.updated_date == datetime.date.today()
    assert product.updated_datetime.date() == datetime.datetime.now().date()
    assert product.data == {}
    assert product.description == ""
    assert product.huge_number == 0
    assert product.price is None
    assert product.status == StatusEnum.DRAFT
    assert product.value is None
    assert product.uuid is None

    await product.update(
        data={"foo": 123},
        value=123.456,
        status=StatusEnum.RELEASED,
        price=decimal.Decimal("999.99"),
        uuid=uuid.UUID("f4e87646-bafa-431e-a0cb-e84f2fcf6b55"),
    )

    product = await Product.query.get()
    assert product.value == 123.456
    assert product.data == {"foo": 123}
    assert product.status == StatusEnum.RELEASED
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
        email="test@saffier.com",
        url="https://saffier.com",
        password="12345",
    )

    user = await User.query.get()
    assert isinstance(user.ipaddress, (ipaddress.IPv4Address, ipaddress.IPv6Address))
    assert user.password == "12345"

    assert user.url == "https://saffier.com"
    await product.update(data={"foo": 1234})
    assert product.updated_datetime != last_updated_datetime
    assert product.updated_date == last_updated_date
