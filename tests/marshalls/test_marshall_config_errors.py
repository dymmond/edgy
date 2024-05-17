import pytest
from anyio import from_thread, sleep
from pydantic import __version__

import edgy
from edgy.core.marshalls import Marshall, fields
from edgy.core.marshalls.config import ConfigMarshall
from edgy.exceptions import MarshallFieldDefinitionError
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio
pydantic_version = __version__[:3]


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    try:
        await models.create_all()
        yield
        await models.drop_all()
    except Exception:
        pytest.skip("No database available")


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


def blocking_function():
    from_thread.run(sleep, 0.1)


class User(edgy.Model):
    name: str = edgy.CharField(max_length=100, null=True)
    email: str = edgy.EmailField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)

    class Meta:
        registry = models


def test_raises_error_on_missing_marshall_config():
    with pytest.raises(MarshallFieldDefinitionError) as raised:

        class UserMarshall(Marshall):
            details: fields.MarshallField = fields.MarshallMethodField(field_type=str)

    assert (
        raised.value.args[0]
        == "The 'marshall_config' was not found. Make sure it is declared and set."
    )


def test_raises_assertation_error_on_using_both_fields_and_exclude():
    with pytest.raises(AssertionError) as raised:

        class UserMarshall(Marshall):
            marshall_config = ConfigMarshall(model=User, fields=["email"], exclude=["language"])
            details: fields.MarshallField = fields.MarshallMethodField(field_type=str)

    assert raised.value.args[0] == "Use either 'fields' or 'exclude', not both."


def test_raises_assertation_error_on_missing_both_fields_and_exclude():
    with pytest.raises(AssertionError) as raised:

        class UserMarshall(Marshall):
            marshall_config = ConfigMarshall(model=User)
            details: fields.MarshallField = fields.MarshallMethodField(field_type=str)

    assert raised.value.args[0] == "Either 'fields' or 'exclude' must be declared."


def test_raises_error_on_missing_declared_function_on_method_field():
    with pytest.raises(MarshallFieldDefinitionError) as raised:

        class UserMarshall(Marshall):
            marshall_config = ConfigMarshall(model=User, fields=["email"])
            details: fields.MarshallField = fields.MarshallMethodField(field_type=str)

    assert (
        raised.value.args[0]
        == "Field 'details' declared but no 'get_details' found in 'UserMarshall'."
    )
