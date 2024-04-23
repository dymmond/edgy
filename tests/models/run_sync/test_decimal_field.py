import decimal
from datetime import date

import pytest

import edgy
from edgy.core.db import fields
from edgy.exceptions import FieldDefinitionError
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = Database(DATABASE_URL)
models = edgy.Registry(database=database)


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


class Employee(edgy.Model):
    name: str = fields.CharField(max_length=255, null=True)
    date_of_birth: date = fields.DateField(auto_now=True)
    salary: decimal.Decimal = fields.DecimalField(max_digits=9, decimal_places=2, null=True)

    class Meta:
        registry = models

    def __str__(self):
        return f"Employee: {self.name}, Age: {self.date_of_birth}, Salary: {self.salary}"


async def test_can_use_decimal_field():
    employee = edgy.run_sync(Employee.query.create(name="Edgy", salary=150000))

    assert employee.salary == 150000


async def test_can_use_decimal_field_raise_exception():
    with pytest.raises(Exception):  # noqa
        edgy.run_sync(Employee.query.create(name="Another", salary=15000000))


async def test_raises_field_definition_error_missing_decimal_places():
    with pytest.raises(FieldDefinitionError):  # noqa

        class AnotherEmployee(edgy.Model):
            name: str = fields.CharField(max_length=255, null=True)
            date_of_birth: date = fields.DateField(auto_now=True)
            salary: decimal.Decimal = fields.DecimalField(max_digits=9, null=True)

            class Meta:
                registry = models

            def __str__(self):
                return f"Employee: {self.name}, Age: {self.date_of_birth}, Salary: {self.salary}"


async def test_raises_field_definition_error_missing_max_digits():
    with pytest.raises(FieldDefinitionError):  # noqa

        class AnotherEmployee(edgy.Model):
            name: str = fields.CharField(max_length=255, null=True)
            date_of_birth: date = fields.DateField(auto_now=True)
            salary: decimal.Decimal = fields.DecimalField(decimal_places=2, null=True)

            class Meta:
                registry = models

            def __str__(self):
                return f"Employee: {self.name}, Age: {self.date_of_birth}, Salary: {self.salary}"


@pytest.mark.parametrize(
    "max_digits,decimal_places", [(-1, None), (None, -2), (None, None), (-1, -2)]
)
async def test_raises_field_definition_error_on_values(max_digits, decimal_places):
    with pytest.raises(FieldDefinitionError):  # noqa

        class AnotherEmployee(edgy.Model):
            name: str = fields.CharField(max_length=255, null=True)
            date_of_birth: date = fields.DateField(auto_now=True)
            salary: decimal.Decimal = fields.DecimalField(
                decimal_places=decimal_places, max_digits=max_digits, null=True
            )

            class Meta:
                registry = models

            def __str__(self):
                return f"Employee: {self.name}, Age: {self.date_of_birth}, Salary: {self.salary}"
