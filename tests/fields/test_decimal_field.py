import decimal
from datetime import date

import pytest

import edgy
from edgy.core.db import fields
from edgy.exceptions import FieldDefinitionError
from edgy.testclient import DatabaseTestClient
from edgy.types import Undefined
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


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


class Employee(edgy.StrictModel):
    name: str = fields.CharField(max_length=255, null=True)
    date_of_birth: date = fields.DateField(auto_now=True)
    salary: decimal.Decimal = fields.DecimalField(
        max_digits=9, decimal_places=2, null=True, strict=False
    )
    salary_btc: decimal.Decimal = fields.DecimalField(
        max_digits=None, decimal_places=None, null=True
    )

    class Meta:
        registry = models

    def __str__(self):
        return f"Employee: {self.name}, Age: {self.date_of_birth}, Salary: {self.salary}"


async def test_can_use_decimal_field():
    employee = await Employee.query.create(
        name="Edgy", salary=150000, salary_btc=decimal.Decimal("10.0002")
    )

    assert employee.salary == 150000
    assert employee.salary_btc == decimal.Decimal("10.0002")


async def test_can_use_decimal_field_raise_exception():
    with pytest.raises(Exception):  # noqa
        await Employee.query.create(name="Another", salary=15000000)


@pytest.mark.parametrize(
    "max_digits,decimal_places", [(1, Undefined), (Undefined, 1), (Undefined, Undefined)]
)
async def test_warn_field_definition_missing_decimal_places(max_digits, decimal_places):
    with pytest.warns(UserWarning):

        class AnotherEmployee(edgy.Model):
            salary: decimal.Decimal = fields.DecimalField(
                max_digits=max_digits, decimal_places=decimal_places, null=True
            )

            class Meta:
                abstract = True


@pytest.mark.parametrize("max_digits,decimal_places", [(-1, None), (None, -2)])
async def test_raises_field_definition_error_on_values(max_digits, decimal_places):
    with pytest.raises(FieldDefinitionError):  # noqa

        class AnotherEmployee(edgy.Model):
            salary: decimal.Decimal = fields.DecimalField(
                decimal_places=decimal_places, max_digits=-1, null=True
            )

            class Meta:
                abstract = True
